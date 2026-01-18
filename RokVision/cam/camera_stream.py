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
        pixel_format = get_config_value("cam_pixel_format", "RGB565")

        # Ensure frame size is reasonable for streaming
        if frame_size_id == 8:  # QXGA is too large for streaming
            frame_size_id = 6  # Use VGA instead

        # Map frame size
        frame_size = FRAME_SIZES.get(frame_size_id, FrameSize.CIF)
        width, height = FRAME_DIMENSIONS.get(frame_size_id, (400, 296))

        # Select pixel format enum
        if pixel_format == "JPEG":
            pixel_format_enum = PixelFormat.JPEG
        else:
            pixel_format_enum = PixelFormat.RGB565

        cam_instance = Camera(
            pixel_format=pixel_format_enum,
            frame_size=frame_size,
            fb_count=2,  # MicroPython framebuffer limit
        )

        # ESP32S3 camera warmup sequence - capture and discard several frames
        # This prevents the initial corrupted/oversized frames that cause DMA overflow
        for warmup_frame in range(5):
            try:
                warmup_capture = cam_instance.capture()
                # Discard warmup frames - they're often corrupted on ESP32S3
                del warmup_capture
                import time
                time.sleep_ms(50)  # Brief pause between warmup captures
            except:
                pass
        
        # Final test capture with validation
        for _ in range(3):  # Try up to 3 times
            test_frame = cam_instance.capture()
            if test_frame and len(test_frame) > 100:  # Ensure frame has data
                break
        else:
            raise Exception("Camera test capture failed after warmup and 3 attempts")

        # Apply camera settings
        apply_camera_settings()

        # Only use software JPEG encoder if not native JPEG
        if pixel_format == "RGB565":
            jpeg_encoder = jpeg.Encoder(
                width=width, height=height, pixel_format="RGB565_BE", quality=quality
            )
        else:
            jpeg_encoder = None
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

    # Send MJPEG headers
    writer.write(
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
        b"Cache-Control: no-store\r\n"
        b"Access-Control-Allow-Origin: *\r\n\r\n"
    )
    await writer.drain()

    try:
        # Fixed frame delay (ms) for FPS cap
        import uasyncio as asyncio
        frame_delay_ms = 40  # 40ms delay (~25 FPS)

        # Calculate expected maximum frame size for DMA overflow prevention
        # ESP32S3 with PSRAM can have issues with oversized JPEG frames
        expected_frame_size = width * height // 4  # Conservative estimate for JPEG
        max_allowed_frame_size = expected_frame_size * 2  # 2x safety margin
        
        import gc
        frame_count = 0
        failed_frames = 0
        oversized_frames = 0
        
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
                        oversized_frames = 0  # Reset oversized counter too
                    await asyncio.sleep_ms(20)  # Longer pause for recovery
                    continue
                
                # Check for oversized frames (ESP32S3 DMA overflow prevention)
                if len(frame) > max_allowed_frame_size:
                    oversized_frames += 1
                    if oversized_frames > 3:  # Too many oversized frames, reinit
                        if not init_camera():
                            break
                        failed_frames = 0
                        oversized_frames = 0
                    continue  # Skip this oversized frame
                
                failed_frames = 0  # Reset failure counter on success
                frame_count += 1

                # Encode frame (handle encoding failures)
                try:
                    if jpeg_encoder:
                        jpeg_frame = jpeg_encoder.encode(frame)
                        if not jpeg_frame or len(jpeg_frame) < 50:  # Invalid JPEG
                            continue
                    else:
                        jpeg_frame = frame
                except Exception:
                    # Encoder failed, skip this frame
                    continue

                # Send frame as single write operation
                frame_header = f"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg_frame)}\r\n\r\n".encode()
                writer.write(frame_header + jpeg_frame + b"\r\n")

                # Drain with timeout
                try:
                    await asyncio.wait_for(writer.drain(), timeout=0.1)
                except asyncio.TimeoutError:
                    # Skip this drain but continue
                    pass
                except Exception:
                    # Connection error, exit
                    break

                # Less frequent GC (every 20 frames) to reduce stuttering on ESP32S3
                if frame_count % 20 == 0:
                    gc.collect()

                # Adaptive delay: longer delay if we're seeing frame issues
                delay_ms = frame_delay_ms
                if oversized_frames > 0 or failed_frames > 0:
                    delay_ms = frame_delay_ms * 2  # Double delay during recovery
                
                await asyncio.sleep_ms(delay_ms)

            except Exception:
                break

    except Exception:
        pass

    finally:
        # Remove from active streams
        active_streams.discard(writer)
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
