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
        print("Camera/JPEG not available")
        return False

    # If camera is already initialized, return success
    if cam_instance is not None:
        print("Camera already initialized")
        return True

    # Try to cleanup any existing camera instance first
    try:
        import gc

        gc.collect()  # Force garbage collection
    except:
        pass

    try:
        # Get camera settings from config - ensure sensible defaults
        frame_size_id = get_config_value("cam_framesize", 4)  # Default QVGA
        quality = get_config_value("cam_quality", 85)  # Default 85%

        # Ensure frame size is reasonable for streaming (not QXGA)
        if frame_size_id == 8:  # QXGA is too large for streaming
            frame_size_id = 6  # Use VGA instead
            print("QXGA not suitable for streaming, using VGA")

        # Map frame size
        frame_size = FRAME_SIZES.get(frame_size_id, FrameSize.QVGA)
        width, height = FRAME_DIMENSIONS.get(frame_size_id, (320, 240))

        print(f"Initializing camera: {width}x{height}, quality={quality}")

        # Initialize camera with RGB565 (confirmed working with RGB565_BE JPEG encoder)
        cam_instance = Camera(
            pixel_format=PixelFormat.RGB565,
            frame_size=frame_size,
            fb_count=2,  # Double buffer
        )

        # Test capture to ensure camera is working
        test_frame = cam_instance.capture()
        if not test_frame:
            raise Exception("Camera test capture failed")
        print(f"Camera test successful - captured {len(test_frame)} bytes")

        # Apply camera settings from config
        apply_camera_settings()

        # Initialize JPEG encoder with RGB565_BE format (confirmed working)
        jpeg_encoder = jpeg.Encoder(
            width=width, height=height, pixel_format="RGB565_BE", quality=quality
        )

        print("Camera and JPEG encoder initialized successfully")
        return True

    except Exception as e:
        print(f"Camera initialization failed: {e}")
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

        print("Camera settings applied")
    except Exception as e:
        print(f"Failed to apply camera settings: {e}")


def reconfigure_camera():
    """Reconfigure camera when admin settings change - clean deinit and reinit"""
    global cam_instance, jpeg_encoder

    try:
        print("Reconfiguring camera...")

        # Clean deinit of existing camera and encoder
        if cam_instance:
            try:
                cam_instance.deinit()
            except Exception as e:
                print(f"Camera deinit warning: {e}")
            cam_instance = None

        if jpeg_encoder:
            jpeg_encoder = None

        # Force garbage collection
        try:
            import gc

            gc.collect()
        except:
            pass

        # Reinitialize everything from scratch
        return init_camera()

    except Exception as e:
        print(f"Camera reconfiguration failed: {e}")
        import sys

        sys.print_exception(e)
        return False


async def stream_handler(reader, writer):
    """Handle MJPEG stream requests"""
    global cam_instance, jpeg_encoder

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

    print("Starting JPEG stream")

    try:
        while True:
            try:
                # Capture frame
                frame = cam_instance.capture()
                if not frame:
                    await asyncio.sleep(0.05)
                    continue

                # Encode to JPEG (use software encoder if available, otherwise assume hardware JPEG)
                if jpeg_encoder:
                    jpeg_frame = jpeg_encoder.encode(frame)
                else:
                    # Assume frame is already JPEG from hardware
                    jpeg_frame = frame

                # Send frame
                writer.write(b"--frame\r\n")
                writer.write(b"Content-Type: image/jpeg\r\n")
                writer.write(f"Content-Length: {len(jpeg_frame)}\r\n\r\n".encode())
                writer.write(jpeg_frame)
                writer.write(b"\r\n")
                await writer.drain()

                await asyncio.sleep(0.05)  # ~20 FPS

            except Exception as e:
                print(f"Stream frame error: {e}")
                break

    except Exception as e:
        print(f"Stream error: {e}")

    finally:
        try:
            await writer.aclose()
        except Exception:
            pass
        print("Stream ended")


def capture_raw_qxga():
    """Capture maximum resolution raw RGB565 data for snapshot conversion

    Returns RGB565 frame buffer data at QXGA resolution (2048x1536)
    that can be converted to JPEG by the web server.
    Temporarily reconfigures the existing camera instance.
    """
    global cam_instance

    if not camera_available or not cam_instance:
        print("Camera not available for raw capture")
        return None

    try:
        # Save current camera configuration
        current_frame_size_id = get_config_value("cam_framesize", 4)
        current_frame_size = FRAME_SIZES.get(current_frame_size_id, FrameSize.QVGA)

        print("Temporarily switching to QXGA for snapshot...")

        # Reconfigure existing camera to QXGA
        cam_instance.reconfigure(
            pixel_format=PixelFormat.RGB565, frame_size=FrameSize.QXGA
        )

        # Capture raw RGB565 frame at QXGA resolution
        rgb565_frame = cam_instance.capture()

        # Restore original camera configuration for streaming
        print("Restoring original camera configuration...")
        cam_instance.reconfigure(
            pixel_format=PixelFormat.RGB565, frame_size=current_frame_size
        )

        if rgb565_frame:
            print(f"Raw QXGA captured: 2048x1536, {len(rgb565_frame)} bytes")
            return rgb565_frame
        else:
            print("Raw QXGA capture failed: no frame data")
            return None

    except Exception as e:
        print(f"Raw QXGA capture failed: {e}")

        # Try to restore original configuration on error
        try:
            current_frame_size_id = get_config_value("cam_framesize", 4)
            current_frame_size = FRAME_SIZES.get(current_frame_size_id, FrameSize.QVGA)
            cam_instance.reconfigure(
                pixel_format=PixelFormat.RGB565, frame_size=current_frame_size
            )
            print("Camera configuration restored after error")
        except Exception:
            print("Failed to restore camera configuration")

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
            # Read request line with timeout
            try:
                req_line = await asyncio.wait_for(reader.readline(), timeout=10)
            except asyncio.TimeoutError:
                print("Request timeout")
                try:
                    await writer.aclose()
                except Exception:
                    pass
                return

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

            # Skip headers with timeout
            try:
                while True:
                    hdr = await asyncio.wait_for(reader.readline(), timeout=5)
                    if not hdr or hdr == b"\r\n":
                        break
            except asyncio.TimeoutError:
                print("Header timeout")
                try:
                    await writer.aclose()
                except Exception:
                    pass
                return

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

        except Exception as e:
            print(f"Stream server request error: {e}")
            try:
                await writer.aclose()
            except Exception:
                pass

    try:
        server = await asyncio.start_server(handle_request, "0.0.0.0", port)
        print(f"Camera stream server started on port {port}")

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
            print("Starting camera stream server...")
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


async def start_camera_stream_async(cfg=None):
    """Start camera stream server as async function"""
    await _stream_server(cfg)
