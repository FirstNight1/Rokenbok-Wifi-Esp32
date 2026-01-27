"""
Clean and simplified camera stream module for RokVision ESP32-S3
Optimized for maximum reliability and minimal memory usage
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
    4: FrameSize.QVGA,   # 320x240 
    5: FrameSize.CIF,    # 400x296
}

# Frame size dimensions for JPEG encoder
FRAME_DIMENSIONS = {
    0: (160, 120),  # QQVGA
    3: (240, 176),  # HQVGA
    4: (320, 240),  # QVGA
    5: (400, 296),  # CIF
}


def init_camera():
    """Initialize camera with current config - simplified and reliable"""
    global cam_instance, jpeg_encoder

    if not camera_available:
        return False

    # Clean up existing instances
    if cam_instance is not None:
        try:
            cam_instance.deinit()
        except:
            pass
        cam_instance = None
    
    if jpeg_encoder is not None:
        try:
            del jpeg_encoder
        except:
            pass
        jpeg_encoder = None

    try:
        # Get camera settings
        frame_size_id = get_config_value("cam_framesize", 5)  # Default CIF
        quality = get_config_value("cam_quality", 85)
        cam_mode = get_config_value("cam_mode", "OV3660_RGB565_SW_JPEG")
        
        # Ensure frame size is in supported range
        if frame_size_id not in FRAME_SIZES:
            frame_size_id = 5  # Default to CIF
        
        # Map frame size
        frame_size = FRAME_SIZES[frame_size_id]
        width, height = FRAME_DIMENSIONS[frame_size_id]
        
        # Simple mode parsing - hardware JPEG or software JPEG
        if cam_mode == "OV2640_JPEG":
            # OV2640 Hardware JPEG
            pixel_format_enum = PixelFormat.JPEG
            use_hardware_jpeg = True
        else:
            # All other modes use RGB565 + software JPEG
            pixel_format_enum = PixelFormat.RGB565
            use_hardware_jpeg = False

        # Initialize camera with minimal configuration
        cam_instance = Camera(
            pixel_format=pixel_format_enum,
            frame_size=frame_size,
            fb_count=1  # Single buffer for simplicity
        )
        
        # Brief pause for camera to stabilize
        import time
        time.sleep_ms(100)
        
        # Test capture
        test_frame = cam_instance.capture()
        if not test_frame or len(test_frame) < 50:
            raise Exception("Camera test capture failed")
        del test_frame
        
        # Apply camera settings
        apply_camera_settings()
        
        # Initialize JPEG encoder only for software JPEG mode
        if not use_hardware_jpeg:
            jpeg_encoder = jpeg.Encoder(
                width=width, height=height, 
                pixel_format="RGB565_BE", 
                quality=quality
            )
        else:
            jpeg_encoder = None
        
        return True

    except Exception as e:
        print(f"Camera initialization failed: {e}")
        if cam_instance:
            try:
                cam_instance.deinit()
            except:
                pass
            cam_instance = None
        if jpeg_encoder:
            try:
                del jpeg_encoder
            except:
                pass
            jpeg_encoder = None
        return False


def apply_camera_settings():
    """Apply camera settings from config"""
    if not cam_instance:
        return
        
    try:
        # Get settings from config
        quality = get_config_value("cam_quality", 85)
        contrast = get_config_value("cam_contrast", 1)
        brightness = get_config_value("cam_brightness", 0)
        saturation = get_config_value("cam_saturation", 0)
        vflip = get_config_value("cam_vflip", 0)
        hmirror = get_config_value("cam_hmirror", 0)
        speffect = get_config_value("cam_speffect", 0)
        
        # Apply settings
        cam_instance.set_quality(quality)
        cam_instance.set_contrast(contrast)
        cam_instance.set_brightness(brightness)
        cam_instance.set_saturation(saturation)
        cam_instance.set_vflip(vflip)
        cam_instance.set_hmirror(hmirror)
        cam_instance.set_special_effect(speffect)
        
    except Exception as e:
        print(f"Failed to apply camera settings: {e}")


async def _send_error(writer, message):
    """Send HTTP error response"""
    try:
        response = f"HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/plain\r\n\r\n{message}"
        writer.write(response.encode())
        await writer.drain()
    except:
        pass


async def stream_handler(reader, writer):
    """Simplified MJPEG stream handler for maximum reliability"""
    global cam_instance, jpeg_encoder, active_streams

    # Add this connection to active streams
    active_streams.add(writer)

    try:
        # Initialize camera if not done
        if not cam_instance and camera_available:
            if not init_camera():
                await _send_error(writer, "Camera initialization failed")
                return

        if not cam_instance:
            await _send_error(writer, "Camera not available")
            return
        
        # Send MJPEG headers
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
            b"Cache-Control: no-store\r\n"
            b"Access-Control-Allow-Origin: *\r\n\r\n"
        )
        await writer.drain()

        frame_count = 0
        frame_delay_ms = 67  # 15 FPS
        
        while writer in active_streams:
            try:
                # Capture frame
                frame = cam_instance.capture()
                if not frame or len(frame) < 50:
                    await asyncio.sleep_ms(100)
                    continue
                
                frame_count += 1

                # Process frame based on mode
                if jpeg_encoder is None:
                    # Hardware JPEG mode - frame is already JPEG
                    jpeg_frame = frame
                else:
                    # Software JPEG mode - encode RGB565 frame
                    try:
                        jpeg_frame = jpeg_encoder.encode(frame)
                        if not jpeg_frame or len(jpeg_frame) < 50:
                            del frame
                            continue
                        # Clean up original RGB565 frame
                        del frame
                    except Exception as e:
                        print(f"JPEG encoding error: {e}")
                        del frame
                        continue

                # Send JPEG frame
                frame_header = f"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg_frame)}\r\n\r\n".encode()
                
                try:
                    writer.write(frame_header + jpeg_frame + b"\r\n")
                    await asyncio.wait_for(writer.drain(), timeout=0.5)
                except Exception as e:
                    del jpeg_frame
                    # Connection lost - client will need to reconnect
                    break
                
                # Cleanup frame data
                del jpeg_frame
                
                # Periodic garbage collection for stability
                if frame_count % 20 == 0:
                    import gc
                    gc.collect()
                
                # Consistent 15 FPS timing
                await asyncio.sleep_ms(frame_delay_ms)

            except Exception as e:
                import gc
                gc.collect()
                await asyncio.sleep_ms(100)

    except Exception as e:
        print(f"Stream handler error: {e}")
    finally:
        active_streams.discard(writer)
        try:
            writer.close()
        except:
            pass


def reconfigure_camera():
    """Reconfigure camera with new settings"""
    return init_camera()


async def start_stream():
    """Start the camera streaming server"""
    global stream_server
    
    if not camera_available:
        return False
        
    try:
        port = get_config_value("cam_stream_port", 8081)
        stream_server = await asyncio.start_server(stream_handler, "0.0.0.0", port)
        return True
    except Exception as e:
        print(f"Failed to start stream server: {e}")
        return False


def stop_all_streams():
    """Stop all active stream connections but keep server running"""
    global active_streams
    
    stopped_count = len(active_streams)
    
    # Close all active connections
    for writer in active_streams.copy():
        try:
            writer.close()
        except:
            pass
    active_streams.clear()
    
    return stopped_count


async def reset_stream():
    """Reset camera stream - stop, reinitialize camera, restart"""
    
    try:
        # Stop current stream
        stop_stream()
        
        # Clean up camera
        cleanup_camera()
        
        # Brief pause to ensure cleanup
        await asyncio.sleep_ms(500)
        
        # Force garbage collection
        import gc
        gc.collect()
        
        # Reinitialize camera
        if init_camera():
            # Restart stream
            if await start_stream():
                return True
            else:
                return False
        else:
            return False
    except Exception as e:
        print(f"Stream reset error: {e}")
        return False


def cleanup_camera():
    """Clean up camera resources"""
    global cam_instance, jpeg_encoder
    
    if cam_instance:
        try:
            cam_instance.deinit()
        except:
            pass
        cam_instance = None
    
    if jpeg_encoder:
        try:
            del jpeg_encoder
        except:
            pass
        jpeg_encoder = None
    
