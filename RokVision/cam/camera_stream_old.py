"""
Camera Stream Module for RokVision (Seeed Studio XIAO ESP32-S3 Sense)

Simple JPEG camera streaming on port 8081.
Requires custom MicroPython firmware with mp_jpeg module.
"""

import uasyncio as asyncio
from RokCommon.variables.vars_store import get_config_value

# Import camera and JPEG modules
try:
    from camera import Camera, FrameSize, PixelFormat
    import jpeg

    camera_available = True
except ImportError as e:
    print(f"Camera or JPEG module not available: {e}")
    camera_available = False
    Camera = None
    FrameSize = None
    PixelFormat = None

# Global instances
cam_instance = None
jpeg_encoder = None

# Stream connection tracking
active_streams = set()
stream_server = None

# Frame size mapping
FRAME_SIZES = {
    0: FrameSize.QQVGA,  # 160x120
    3: FrameSize.HQVGA,  # 240x176
    4: FrameSize.QVGA,  # 320x240 (default)
    5: FrameSize.CIF,  # 400x296
    6: FrameSize.VGA,  # 640x480
    7: FrameSize.SVGA,  # 800x600
    8: FrameSize.QXGA,  # 2048x1536 (maximum resolution)
}

# Frame size dimensions for JPEG encoder
FRAME_DIMENSIONS = {
    0: (160, 120),  # QQVGA
    3: (240, 176),  # HQVGA
    4: (320, 240),  # QVGA
    5: (400, 296),  # CIF
    6: (640, 480),  # VGA
    7: (800, 600),  # SVGA
    8: (2048, 1536),  # QXGA
}


def init_camera():
    """Initialize camera with current config - only if not already initialized"""
    global cam_instance, jpeg_encoder

    if not camera_available:
        return False

    # If camera is already initialized, return success
    if cam_instance is not None:
        return True

    # Minimal cleanup
    try:
        import gc
        gc.collect()
    except:
        pass

    try:
        from RokCommon.variables.vars_store import get_config_value

        # Get camera settings from config
        frame_size_id = get_config_value("cam_framesize", 5)  # Default CIF
        quality = get_config_value("cam_quality", 85)
        cam_mode = get_config_value("cam_mode", "OV3660_RGB565_SW_JPEG")

        print(f"[CAMERA] Initializing with mode: {cam_mode}")

        # Parse camera mode - simplified to hardware vs software JPEG only
        cam_mode = get_config_value("cam_mode", "OV3660_RGB565_SW_JPEG")
        
        if cam_mode == "OV2640_JPEG":
            # OV2640 Hardware JPEG mode
            pixel_format_enum = PixelFormat.JPEG
            use_hardware_jpeg = True
            print(f"[CAMERA] OV2640 hardware JPEG mode at resolution {frame_size_id}")
        else:
            # All other modes use RGB565 + software JPEG
            pixel_format_enum = PixelFormat.RGB565
            use_hardware_jpeg = False
            print(f"[CAMERA] Software JPEG mode ({cam_mode}) at resolution {frame_size_id}")

        # Ensure frame size is reasonable for streaming
        if frame_size_id == 8:  # QXGA is too large for streaming
            frame_size_id = 6  # Use VGA instead

        # Map frame size
        frame_size = FRAME_SIZES.get(frame_size_id, FrameSize.CIF)
        width, height = FRAME_DIMENSIONS.get(frame_size_id, (400, 296))
        
        print(f"[CAMERA] Initializing camera: {width}x{height}, pixel_format={pixel_format_enum}")

        # Initialize camera with minimal configuration
        cam_instance = Camera(
            pixel_format=pixel_format_enum,
            frame_size=frame_size,
            fb_count=1  # Single buffer for simplicity and memory efficiency
        )
        
        # Brief initialization delay
        import time
        time.sleep_ms(100)
        
        # Single test capture to verify camera is working
        test_frame = cam_instance.capture()
        if not test_frame or len(test_frame) < 50:
            raise Exception("Camera test capture failed")
        del test_frame
        
        # Apply camera settings
        apply_camera_settings()

        # Initialize JPEG encoder ONLY for software JPEG mode
        if use_hardware_jpeg:
            jpeg_encoder = None
            print("[CAMERA] Hardware JPEG mode - no software encoder needed")
        else:
            try:
                jpeg_encoder = jpeg.Encoder(
                    width=width, height=height, pixel_format="RGB565_BE", quality=quality
                )
                print(f"[CAMERA] Software JPEG encoder initialized: {width}x{height}, quality={quality}")
            except Exception as e:
                print(f"[CAMERA] Failed to initialize JPEG encoder: {e}")
                cam_instance.deinit()
                cam_instance = None
                return False
        
        print(f"[CAMERA] Initialization complete: format={pixel_format}, framesize={frame_size_id} ({width}x{height})")
        return True

    except Exception:
        cam_instance = None
        jpeg_encoder = None
        return False


def apply_camera_settings():
    """Apply camera settings from config"""
    if not cam_instance:
        return

    try:
        # Apply settings with bounds checking
        contrast = max(-2, min(2, get_config_value("cam_contrast", 0)))
        brightness = max(-2, min(2, get_config_value("cam_brightness", 0)))
        saturation = max(-2, min(2, get_config_value("cam_saturation", 0)))
        vflip = bool(get_config_value("cam_vflip", 0))
        hmirror = bool(get_config_value("cam_hmirror", 0))
        special_effect = get_config_value("cam_speffect", 0)

        cam_instance.contrast = contrast
        cam_instance.brightness = brightness
        cam_instance.saturation = saturation
        cam_instance.vflip = vflip
        cam_instance.hmirror = hmirror
        cam_instance.special_effect = special_effect

    except Exception:
        pass


def reconfigure_camera():
    """Reconfigure camera when admin settings change - clean deinit and reinit"""
    global cam_instance, jpeg_encoder

    try:
        # Clean deinit of existing camera and encoder
        if cam_instance:
            try:
                cam_instance.deinit()
            except Exception:
                pass
            cam_instance = None

        if jpeg_encoder:
            jpeg_encoder = None

        # Force garbage collection and brief pause
        try:
            import gc
            gc.collect()
            import uasyncio as asyncio
            # Brief pause to let hardware reset
            import time
            time.sleep_ms(100)
        except:
            pass

        # Reinitialize everything from scratch
        return init_camera()

    except Exception:
        return False


def stop_active_streams():
    """Stop all active stream connections gracefully"""
    global active_streams
    
    # Create a copy to avoid modification during iteration
    streams_to_close = list(active_streams)
    active_streams.clear()
    
    # Close connections
    for writer in streams_to_close:
        try:
            if hasattr(writer, 'aclose'):
                writer.aclose()
        except Exception:
            pass


def reset_camera_on_corruption():
    """Reset camera when corruption is detected"""
    global cam_instance, jpeg_encoder
    
    try:
        # Stop all active streams first
        stop_active_streams()
        
        # Clean deinit
        if cam_instance:
            cam_instance.deinit()
            cam_instance = None
        
        if jpeg_encoder:
            jpeg_encoder = None
            
        # Force cleanup and pause
        import gc
        gc.collect()
        import time
        time.sleep_ms(200)  # Longer pause for hardware reset
        
        # Reinitialize
        return init_camera()
    except Exception:
        return False


async def stream_handler(reader, writer):
    """Handle MJPEG stream requests"""
    global cam_instance, jpeg_encoder, active_streams

    # Add this connection to active streams
    active_streams.add(writer)

    # Initialize camera if not done
    if not cam_instance and camera_available:
        if not init_camera():
            await _send_error(writer, "Camera initialization failed")
            active_streams.discard(writer)
            return

    if not cam_instance:
        await _send_error(writer, "Camera not available")
        active_streams.discard(writer)
        return

    # Check current camera mode for streaming type
    cam_mode = get_config_value("cam_mode", "OV3660_RGB565_SW_JPEG")
    
    # Note: Raw RGB565 streaming disabled - browsers don't support it properly
    # Force MJPEG streaming for all modes
    use_raw_streaming = False
    
    print(f"[STREAM] Starting stream with mode: {cam_mode}, using MJPEG format")
    
    # Send MJPEG headers for all streaming modes
    print("[STREAM] Using MJPEG streaming headers")
    writer.write(
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
        b"Cache-Control: no-store\r\n"
        b"Access-Control-Allow-Origin: *\r\n\r\n"
    )
    await writer.drain()

    try:
        # Frame rate limiting for stable streaming and memory management
        import uasyncio as asyncio
        frame_delay_ms = 67  # ~15 FPS (1000ms / 15 = 67ms per frame)

        import gc
        frame_count = 0
        failed_frames = 0
        last_gc_frame = 0
        
        print(f"[STREAM] Starting stream at ~15 FPS (67ms frame delay) for stable memory management")
        
        while writer in active_streams:
            try:
                # Capture frame with validation
                frame = cam_instance.capture()
                if not frame or len(frame) < 100:  # Invalid/empty frame
                    failed_frames += 1
                    if failed_frames > 10:  # Too many failures, reinit camera
                        if not init_camera():
                            break
                        failed_frames = 0
                    await asyncio.sleep_ms(20)  # Longer pause for recovery
                    continue
                
                # Basic frame size check (reject extremely large frames > 500KB)
                if len(frame) > 500000:  # 500KB limit to prevent memory issues
                    failed_frames += 1
                    # Force immediate cleanup of bad frame
                    del frame
                    gc.collect()
                    continue  # Skip this oversized frame
                
                failed_frames = 0  # Reset failure counter on success
                frame_count += 1

                # Proactive memory management for long-term stability
                if frame_count - last_gc_frame >= 10:  # GC every 10 frames
                    import gc
                    gc.collect()
                    last_gc_frame = frame_count
                    
                # Memory monitoring every 50 frames to detect issues early
                if frame_count % 50 == 0:
                    try:
                        import micropython
                        print(f"[MEMORY] Frame {frame_count} memory status:")
                        micropython.mem_info()
                    except:
                        pass  # Don't let memory monitoring break the stream

                # Process frame based on mode - simplified logic
                if jpeg_encoder is None:
                    # Hardware JPEG mode - frame is already JPEG
                    jpeg_frame = frame
                    if frame_count % 100 == 0:
                        print(f"[STREAM] HW JPEG frame #{frame_count}: {len(jpeg_frame)} bytes")
                else:
                    # Software JPEG mode - encode RGB565 frame
                    try:
                        jpeg_frame = jpeg_encoder.encode(frame)
                        if not jpeg_frame or len(jpeg_frame) < 50:
                            print(f"[STREAM] SW JPEG encoding failed at frame #{frame_count}")
                            del frame
                            continue
                        if frame_count % 100 == 0:
                            print(f"[STREAM] SW JPEG frame #{frame_count}: {len(jpeg_frame)} bytes")
                    except Exception as e:
                        print(f"[STREAM] JPEG encoding error at frame #{frame_count}: {e}")
                        del frame
                        continue
                
                # Clean up original frame if different from JPEG frame
                if frame != jpeg_frame:
                    del frame

                # Send JPEG frame
                frame_header = f"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg_frame)}\r\n\r\n".encode()
                
                try:
                    writer.write(frame_header + jpeg_frame + b"\r\n")
                    await asyncio.wait_for(writer.drain(), timeout=0.1)
                except Exception as e:
                    print(f"[STREAM] Connection error at frame {frame_count}: {e}")
                    del jpeg_frame
                    break
                
                # Cleanup frame data
                del jpeg_frame
                
                # Garbage collect every 20 frames for stability
                if frame_count % 20 == 0:
                    import gc
                    gc.collect()
                
                # Consistent 15 FPS timing
                await asyncio.sleep_ms(frame_delay_ms)

            except Exception as e:
                print(f"[STREAM] Frame processing error: {e}")
                import gc
                gc.collect()
                await asyncio.sleep_ms(100)  # Brief pause on error

    except Exception:
        pass

    finally:
        # Aggressive cleanup to prevent memory corruption
        active_streams.discard(writer)
        
        # Force garbage collection before closing
        import gc
        gc.collect()
        
        try:
            await writer.aclose()
        except Exception:
            pass


def capture_raw_qxga():
    """Capture maximum resolution raw RGB565 data for snapshot conversion

    Returns RGB565 frame buffer data at QXGA resolution (2048x1536)
    that can be converted to JPEG by the web server.
    Temporarily reconfigures the existing camera instance.
    """
    global cam_instance

    if not camera_available or not cam_instance:
        return None

    try:
        # Save current camera configuration
        current_frame_size_id = get_config_value("cam_framesize", 4)
        current_frame_size = FRAME_SIZES.get(current_frame_size_id, FrameSize.QVGA)

        # Reconfigure existing camera to QXGA
        cam_instance.reconfigure(
            pixel_format=PixelFormat.RGB565, frame_size=FrameSize.QXGA
        )

        # Capture raw RGB565 frame at QXGA resolution
        rgb565_frame = cam_instance.capture()

        # Restore original camera configuration for streaming
        cam_instance.reconfigure(
            pixel_format=PixelFormat.RGB565, frame_size=current_frame_size
        )

        if rgb565_frame:
            return rgb565_frame
        else:
            return None

    except Exception:
        # Try to restore original configuration on error
        try:
            current_frame_size_id = get_config_value("cam_framesize", 4)
            current_frame_size = FRAME_SIZES.get(current_frame_size_id, FrameSize.QVGA)
            cam_instance.reconfigure(
                pixel_format=PixelFormat.RGB565, frame_size=current_frame_size
            )
        except Exception:
            pass
        return None
        return None


async def _send_error(writer, message):
    """Send error response"""
    response = f"HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/plain\r\n\r\n{message}"
    writer.write(response.encode())
    await writer.drain()
    await writer.aclose()


async def _stream_server(cfg=None):
    """Dedicated stream server on configurable port (default 8081)"""

    # Get port from config or use default
    if cfg is None:
        port = get_config_value("cam_stream_port", 8081)
    else:
        port = cfg.get("cam_stream_port", 8081)

    async def handle_request(reader, writer):
        try:
            # Read request line
            req_line = await reader.readline()
            if not req_line:
                try:
                    await writer.aclose()
                except Exception:
                    pass
                return

            line = req_line.decode().strip()
            parts = line.split()
            if len(parts) < 2:
                try:
                    await writer.aclose()
                except Exception:
                    pass
                return

            path = parts[1]

            # Skip headers
            while True:
                hdr = await reader.readline()
                if not hdr or hdr == b"\r\n":
                    break

            # Only serve /stream endpoint
            if path == "/stream":
                await stream_handler(reader, writer)
            else:
                try:
                    writer.write(
                        b"HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\n\r\nOnly /stream available on this port"
                    )
                    await writer.drain()
                    await writer.aclose()
                except Exception:
                    pass

        except Exception:
            try:
                await writer.aclose()
            except Exception:
                pass

    try:
        server = await asyncio.start_server(handle_request, "0.0.0.0", port)

        # Keep server running
        while True:
            await asyncio.sleep(3600)

    except Exception as e:
        print(f"Failed to start stream server on port {port}: {e}")
        raise  # Re-raise to propagate the error properly


def start_camera_stream(cfg=None):
    """Start camera stream server on configurable port in separate thread"""

    async def camera_main():
        try:
            await _stream_server(cfg)
        except Exception as e:
            print(f"Camera stream server error: {e}")
            import sys

            sys.print_exception(e)

    try:
        # Import and use uasyncio directly in thread context
        import uasyncio as asyncio

        # Create a simple event loop for this thread
        async def run_forever():
            await camera_main()

        # Use create_task and run_forever pattern
        loop = asyncio.get_event_loop()
        task = loop.create_task(run_forever())
        loop.run_forever()

    except Exception as e:
        print(f"Failed to start camera stream: {e}")
        import sys

        sys.print_exception(e)



def stop_all_streams():
    """Stop all active stream connections"""
    global active_streams
    count = len(active_streams)
    active_streams.clear()
    return count


async def start_camera_stream_async(cfg=None):
    """Start camera stream server as async function"""
    await _stream_server(cfg)
