from RokCommon.variables.vars_store import get_config_value, save_config_value
from RokCommon.variables.vehicle_types import VEHICLE_TYPES
from RokCommon.web.request_response import Request, Response
from RokCommon.web import PageHandler
from RokCommon.web.pages.home_page import load_and_process_header
import random

# Import camera reconfiguration function
try:
    from cam.camera_stream import reconfigure_camera
    # Additional imports for snapshot functionality
    from camera import Camera, FrameSize, PixelFormat
    import jpeg
    camera_available = True
except ImportError:
    print("Camera module not available for admin page")
    reconfigure_camera = None
    camera_available = False

    def reconfigure_camera():
        return False


def _valid_vehicle_types():
    """Return set of valid vehicle type names"""
    return {t["typeName"] for t in VEHICLE_TYPES}


class AdminPageHandler(PageHandler):
    """Admin page handler using unified Request/Response system"""

    def handle_get(self, request):
        """Handle GET requests for admin page"""
        try:
            cfg = {
                "vehicleType": get_config_value("vehicleType"),
                "vehicleTag": get_config_value("vehicleTag"),
                "vehicleName": get_config_value("vehicleName"),
                "ledEnabled": get_config_value("ledEnabled", True),
                "ledPin": get_config_value("ledPin", 9),
                "cam_mode": get_config_value("cam_mode", "OV3660_RGB565_SW_JPEG"),
                "cam_framesize": get_config_value("cam_framesize", 4),
                "cam_quality": get_config_value("cam_quality", 85),
                "cam_contrast": get_config_value("cam_contrast", 0),
                "cam_brightness": get_config_value("cam_brightness", 0),
                "cam_saturation": get_config_value("cam_saturation", 0),
                "cam_vflip": get_config_value("cam_vflip", 0),
                "cam_hmirror": get_config_value("cam_hmirror", 0),
                "cam_speffect": get_config_value("cam_speffect", 0),
                "cam_stream_port": get_config_value("cam_stream_port", 8081),
            }
            html = build_admin_page(cfg)
            return Response.html(html)
        except Exception as e:
            print(f"Admin page GET error: {e}")
            return Response.server_error(f"Admin page error: {e}")

    def handle_post(self, request):
        """Handle POST requests for admin page"""
        try:
            # Use existing handle_post logic
            result = handle_post_legacy(request.body, {})

            # Return redirect response
            if result and len(result) > 1:
                redirect_path = result[1]
                return Response.redirect_to(redirect_path)
            else:
                return Response.redirect_to("/admin")

        except Exception as e:
            print(f"Admin page POST error: {e}")
            return Response.server_error(f"Admin page POST error: {e}")


# Create handler instance
admin_handler = AdminPageHandler()


def handle_post_legacy(body, cfg):
    """Legacy handle_post function"""
    """Handle POST requests for admin settings"""
    valid_types = _valid_vehicle_types()

    # Basic x-www-form-urlencoded decode
    fields = {}
    for pair in body.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            fields[k] = v.replace("+", " ")

    # Cancel → no changes saved
    if "cancel" in fields:
        return None, "/admin"

    # Validate vehicle type
    new_type = fields.get("vehicleType", get_config_value("vehicleType"))
    if new_type not in valid_types:
        print("⚠️ Invalid vehicleType received:", new_type)
        return None, "/admin"

    old_type = get_config_value("vehicleType")
    old_tag = get_config_value("vehicleTag", "")

    # Find tagName for old and new type
    old_type_obj = next((t for t in VEHICLE_TYPES if t["typeName"] == old_type), None)
    new_type_obj = next((t for t in VEHICLE_TYPES if t["typeName"] == new_type), None)
    old_tag_prefix = old_type_obj["tagName"] if old_type_obj else old_type
    new_tag_prefix = new_type_obj["tagName"] if new_type_obj else new_type

    # Special case: if new_type is 'fpv', tag should be 'RokVision-XXXXXX'
    if new_type == "fpv":
        new_tag_prefix = "RokVision"

    # Update tag if vehicle type changed
    if new_type == "fpv":
        # For FPV type, use RokVision-XXXXXX format
        # Only generate new tag if current tag doesn't already use RokVision format
        if (
            old_tag.startswith("RokVision-") and len(old_tag) == 17
        ):  # RokVision-XXXXXX (17 chars)
            new_tag = old_tag  # Keep existing RokVision tag
        else:
            # Generate new RokVision tag only if needed
            chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            suffix = "".join(random.choice(chars) for _ in range(6))
            new_tag = f"RokVision-{suffix}"
    elif old_tag.startswith(old_tag_prefix + "-"):
        suffix = old_tag[len(old_tag_prefix) + 1 :]
        new_tag = new_tag_prefix + "-" + suffix
    else:
        new_tag = old_tag

    # If user manually changed vehicleTag, use their value
    tag_from_form = fields.get("vehicleTag")
    if tag_from_form is not None and tag_from_form != old_tag:
        new_tag = tag_from_form

    # Camera type dropdown logic
    # Save camera mode and derive individual settings
    cam_mode = fields.get("cam_mode", get_config_value("cam_mode", "OV3660_RGB565_SW_JPEG"))
    save_config_value("cam_mode", cam_mode)
    
    # Derive pixel format and camera type from mode
    if cam_mode.startswith("OV2640"):
        save_config_value("cam_type", "OV2640")
        if cam_mode == "OV2640_JPEG":
            save_config_value("cam_pixel_format", "JPEG")
        else:
            save_config_value("cam_pixel_format", "RGB565")
    else:  # OV3660
        save_config_value("cam_type", "OV3660")
        save_config_value("cam_pixel_format", "RGB565")

    # Save settings
    save_config_value("vehicleType", new_type)
    save_config_value("vehicleTag", new_tag)
    save_config_value(
        "vehicleName", fields.get("vehicleName", get_config_value("vehicleName"))
    )

    # Camera settings
    save_config_value(
        "cam_framesize",
        int(fields.get("cam_framesize", get_config_value("cam_framesize", 4))),
    )
    save_config_value(
        "cam_quality",
        int(fields.get("cam_quality", get_config_value("cam_quality", 85))),
    )
    save_config_value(
        "cam_contrast",
        int(fields.get("cam_contrast", get_config_value("cam_contrast", 0))),
    )
    save_config_value(
        "cam_brightness",
        int(fields.get("cam_brightness", get_config_value("cam_brightness", 0))),
    )
    save_config_value(
        "cam_saturation",
        int(fields.get("cam_saturation", get_config_value("cam_saturation", 0))),
    )
    save_config_value("cam_vflip", 1 if "cam_vflip" in fields else 0)
    save_config_value("cam_hmirror", 1 if "cam_hmirror" in fields else 0)
    save_config_value(
        "cam_speffect",
        int(fields.get("cam_speffect", get_config_value("cam_speffect", 0))),
    )
    save_config_value(
        "cam_stream_port",
        int(fields.get("cam_stream_port", get_config_value("cam_stream_port", 8081))),
    )

    # LED settings
    save_config_value("ledEnabled", 1 if "ledEnabled" in fields else 0)
    led_pin = int(fields.get("ledPin", get_config_value("ledPin", 9)))
    save_config_value("ledPin", led_pin)

    # Update network LED configuration if changed
    try:
        from RokCommon.control.network_led import get_network_led
        network_led = get_network_led()
        if network_led:
            led_enabled = 1 if "ledEnabled" in fields else 0
            if led_enabled and led_pin != -1:
                network_led.reinit_with_pin(led_pin)
                # reinit_with_pin now includes automatic status update
            else:
                network_led.set_override(True, False)  # Turn off
    except Exception as e:
        print(f"LED reconfiguration failed: {e}")

    # Trigger camera reconfiguration with new settings
    if camera_available:
        try:
            reconfigure_camera()
        except Exception as e:
            print(f"Camera reconfiguration failed: {e}")

    return None, "/admin"


# Make unified handler accessible as module functions
handle_get = admin_handler.handle_get
handle_post = admin_handler.handle_post



def build_admin_page(cfg):
    """Build the admin page HTML with current configuration"""
    try:
        # Load header navigation using shared function
        header_nav = load_and_process_header(cfg.get("vehicleName", ""))
        if not header_nav:
            header_nav = "<div>Header not found</div>"

        # Load template helper function
        def _load_template(path):
            """Load template with fallback paths"""
            from RokCommon.web.static_assets import load_template

            # For project-specific templates, try relative path first
            if (
                "admin_page.html" in path
                or "testing_page.html" in path
                or "play_page.html" in path
            ):
                content = load_template(path)
                if content is not None:
                    return content
                # Don't try RokCommon path for project-specific templates
                return None

            # For common templates, try RokCommon path first
            content = load_template(f"RokCommon/{path}")
            if content is not None:
                return content
            # Fallback to relative path
            content = load_template(path)
            if content is not None:
                return content
            return None

        # Build vehicle type options
        type_options = "".join(
            [
                f"<option value='{t['typeName']}' {'selected' if cfg.get('vehicleType') == t['typeName'] else ''}>{t['typeFriendlyName']}</option>"
                for t in VEHICLE_TYPES
            ]
        )

        # Build vehicle type mapping for JavaScript
        vehicle_type_map = {}
        for t in VEHICLE_TYPES:
            if t["typeName"] == "fpv":
                vehicle_type_map[t["typeName"]] = "RokVision"
            else:
                vehicle_type_map[t["typeName"]] = t["tagName"]

        # Convert to JavaScript object properties (comma-separated key-value pairs)
        vehicle_type_js = ", ".join(
            [
                f'"{type_name}": "{tag_prefix}"'
                for type_name, tag_prefix in vehicle_type_map.items()
            ]
        )

        # Camera mode dropdown with all supported options
        cam_mode = cfg.get("cam_mode", "OV3660_RGB565_SW_JPEG")
        cam_mode_options = []
        mode_options = [
            ("OV2640_JPEG", "OV2640 - Hardware JPEG"),
            ("OV3660_RGB565", "OV3660 - RGB565 + Software JPEG"),
            ("OV3660_RGB565_SW_JPEG", "OV3660 - RGB565 + Software JPEG")
        ]
        for val, label in mode_options:
            selected = "selected" if cam_mode == val else ""
            cam_mode_options.append(f'<option value="{val}" {selected}>{label}</option>')
        cam_mode_options_html = "\n                    ".join(cam_mode_options)

        # Load main admin page template
        html = _load_template("web/pages/assets/admin_page.html")
        if not html:
            return "<html><body><h2>Admin page template not found</h2></body></html>"

        # Replace template variables
        framesize = str(cfg.get("cam_framesize", 4))
        quality = str(cfg.get("cam_quality", 85))
        contrast = str(cfg.get("cam_contrast", 0))
        brightness = str(cfg.get("cam_brightness", 0))
        saturation = str(cfg.get("cam_saturation", 0))
        vflip = str(cfg.get("cam_vflip", 0))
        hmirror = str(cfg.get("cam_hmirror", 0))
        speffect = str(cfg.get("cam_speffect", 0))
        stream_port = str(cfg.get("cam_stream_port", 8081))

        # Build framesize options with proper selection
        framesize_options = []
        framesize_choices = [
            ("0", "QQVGA (160x120)"),
            ("3", "HQVGA (240x176)"),
            ("4", "QVGA (320x240) - Recommended"),
            ("5", "CIF (400x296)")
        ]

        for value, label in framesize_choices:
            selected = "selected" if value == framesize else ""
            framesize_options.append(
                f'<option value="{value}" {selected}>{label}</option>'
            )
        framesize_options_html = "\n                    ".join(framesize_options)

        # Build special effect options
        speffect_options = []
        speffect_choices = [
            ("0", "None"),
            ("2", "Grayscale"),
            ("3", "Red Tint"),
            ("4", "Green Tint"),
            ("5", "Blue Tint"),
            ("6", "Sepia"),
        ]

        for value, label in speffect_choices:
            selected = "selected" if value == speffect else ""
            speffect_options.append(
                f'<option value="{value}" {selected}>{label}</option>'
            )
        speffect_options_html = "\n                    ".join(speffect_options)
        # Generate checkbox states
        vflip_checked = "checked" if vflip == "1" else ""
        hmirror_checked = "checked" if hmirror == "1" else ""
        
        # LED settings
        led_enabled = cfg.get("ledEnabled", True)
        led_pin = cfg.get("ledPin", 9)
        led_enabled_checked = "checked" if led_enabled else ""
        
        # Build LED pin dropdown using standard ESP32-S3 mapping
        from RokCommon.control.network_led import NETWORK_LED_PINS
        available_pins = [1, 2, 3, 4, 5, 6, 43, 44, 7, 8, 9, 10, 21, 41, 42]
        led_pin_options = "<option value='-1' {}>Disabled</option>".format("selected" if led_pin == -1 else "")
        for pin in available_pins:
            selected = "selected" if pin == led_pin else ""
            pin_name = NETWORK_LED_PINS.get(pin, f"GPIO{pin}")
            led_pin_options += f"<option value='{pin}' {selected}>{pin_name}</option>"

        replacements = {
            "{{ header_nav }}": header_nav,
            "{{ type_options }}": type_options,
            "{{ vehicle_tag }}": cfg.get("vehicleTag", "") or "",
            "{{ vehicle_name }}": cfg.get("vehicleName", "") or "",
            "{{ framesize_options }}": framesize_options_html,
            "{{ cam_mode_options }}": cam_mode_options_html,
            "{{ speffect_options }}": speffect_options_html,
            "{{ vflip_checked }}": vflip_checked,
            "{{ hmirror_checked }}": hmirror_checked,
            "{{ cam_framesize }}": framesize,
            "{{ cam_quality }}": quality,
            "{{ cam_contrast }}": contrast,
            "{{ cam_brightness }}": brightness,
            "{{ cam_saturation }}": saturation,
            "{{ cam_vflip }}": vflip,
            "{{ cam_hmirror }}": hmirror,
            "{{ cam_speffect }}": speffect,
            "{{ cam_stream_port }}": stream_port,
            "{{ led_enabled_checked }}": led_enabled_checked,
            "{{ led_pin_options }}": led_pin_options,
            "{{vehicle_type_map}}": vehicle_type_js,
        }

        for placeholder, value in replacements.items():
            html = html.replace(placeholder, value)

        return html

    except Exception as e:
        print(f"Error building admin page: {e}")
        return f"<html><body><h2>Error loading admin page: {e}</h2></body></html>"


async def snapshot_handler(request):
    """Capture high-resolution snapshot with dedicated camera instance"""
    
    if not camera_available:
        return Response(
            status="500 Internal Server Error",
            content_type="text/plain",
            body="Camera not available"
        )
    
    try:
        # Determine camera type and maximum resolution
        cam_mode = get_config_value("cam_mode", "OV3660_RGB565_SW_JPEG")
        
        if cam_mode.startswith("OV2640"):
            # OV2640 - use SXGA (1280x1024) for reliable high-resolution snapshots
            frame_size = FrameSize.SXGA
            width, height = 1280, 1024
            camera_type = "OV2640 (1.3MP)"
        else:
            # OV3660 is 3MP sensor - use QXGA (2048x1536) for maximum resolution  
            frame_size = FrameSize.QXGA
            width, height = 2048, 1536
            camera_type = "OV3660 (3MP)"
        
        # Stop streaming camera to free hardware for snapshot
        try:
            from cam.camera_stream import cleanup_camera
            cleanup_camera()
        except Exception as e:
            print(f"Warning: Failed to cleanup streaming camera: {e}")
        
        # Create dedicated snapshot camera instance (hardware exclusive)
        snapshot_cam = Camera(
            pixel_format=PixelFormat.RGB565,
            frame_size=frame_size,
            fb_count=1
        )
        
        # Let camera stabilize before applying settings
        import time
        time.sleep_ms(200)
        
        # Apply current camera settings to snapshot camera
        quality = get_config_value("cam_quality", 95)  # Higher quality for snapshots
        contrast = get_config_value("cam_contrast", 1)
        brightness = get_config_value("cam_brightness", 0)
        saturation = get_config_value("cam_saturation", 0)
        vflip = get_config_value("cam_vflip", 0)
        hmirror = get_config_value("cam_hmirror", 0)
        speffect = get_config_value("cam_speffect", 0)
        
        snapshot_cam.set_quality(quality)
        snapshot_cam.set_contrast(contrast)
        snapshot_cam.set_brightness(brightness)
        snapshot_cam.set_saturation(saturation)
        snapshot_cam.set_vflip(vflip)
        snapshot_cam.set_hmirror(hmirror)
        snapshot_cam.set_special_effect(speffect)
        
        # Test camera capture before creating encoder
        test_frame = snapshot_cam.capture()
        if not test_frame or len(test_frame) < 1000:
            raise Exception("Failed to capture initial frame. Camera may be busy or misconfigured.")
        del test_frame
        
        # Create dedicated JPEG encoder for this snapshot
        jpeg_encoder = jpeg.Encoder(
            width=width, height=height, 
            pixel_format="RGB565_BE", 
            quality=quality
        )
        
        # Brief pause for camera to stabilize
        import time
        time.sleep_ms(100)
        
        # Capture frame
        frame = snapshot_cam.capture()
        if not frame or len(frame) < 1000:
            raise Exception("Failed to capture valid high-res frame")
        
        # Encode as JPEG
        jpeg_frame = jpeg_encoder.encode(frame)
        if not jpeg_frame or len(jpeg_frame) < 100:
            raise Exception("Failed to encode high-res JPEG")
        
        # Clean up all resources immediately
        del frame
        snapshot_cam.deinit()
        del snapshot_cam
        del jpeg_encoder
        
        # Force garbage collection
        import gc
        gc.collect()
        
        # Restart streaming camera - must deinit/reinit camera hardware for resolution change
        try:
            from cam.camera_stream import cleanup_camera, init_camera
            
            # Brief pause for cleanup
            import uasyncio as asyncio
            await asyncio.sleep_ms(500)
            
            # Reinitialize streaming camera at original resolution
            init_camera()
                
        except Exception as restart_error:
            print(f"Camera restart error: {restart_error}")
            # Continue anyway - snapshot was successful
        
        # Return JPEG image
        return Response(
            status="200 OK",
            content_type="image/jpeg",
            body=jpeg_frame
        )
        
    except Exception as e:
        print(f"Snapshot error: {e}")
        # Ensure cleanup on error
        try:
            if 'snapshot_cam' in locals():
                snapshot_cam.deinit()
            if 'frame' in locals():
                del frame
            if 'jpeg_encoder' in locals():
                del jpeg_encoder
        except:
            pass
        return Response(
            status="500 Internal Server Error",
            content_type="text/plain",
            body=f"Snapshot failed: {e}"
        )
