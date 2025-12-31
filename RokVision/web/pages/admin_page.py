from variables.vars_store import load_config, save_config
from variables.vehicle_types import VEHICLE_TYPES
import random

# Import camera reconfiguration function
try:
    from cam.camera_stream import reconfigure_camera

    camera_available = True
except ImportError:
    print("Camera module not available for admin page")
    camera_available = False

    def reconfigure_camera():
        return False


def handle_post(body, cfg):
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
        return cfg, "/admin"

    # Validate vehicle type
    new_type = fields.get("vehicleType", cfg.get("vehicleType"))
    if new_type not in valid_types:
        print("⚠️ Invalid vehicleType received:", new_type)
        return cfg, "/admin"

    old_type = cfg.get("vehicleType")
    old_tag = cfg.get("vehicleTag", "")

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

    # Save settings
    cfg["vehicleType"] = new_type
    cfg["vehicleTag"] = new_tag
    cfg["vehicleName"] = fields.get("vehicleName", cfg.get("vehicleName"))

    # Camera settings
    cfg["cam_framesize"] = int(fields.get("cam_framesize", cfg.get("cam_framesize", 4)))
    cfg["cam_quality"] = int(fields.get("cam_quality", cfg.get("cam_quality", 85)))
    cfg["cam_contrast"] = int(fields.get("cam_contrast", cfg.get("cam_contrast", 0)))
    cfg["cam_brightness"] = int(
        fields.get("cam_brightness", cfg.get("cam_brightness", 0))
    )
    cfg["cam_saturation"] = int(
        fields.get("cam_saturation", cfg.get("cam_saturation", 0))
    )
    cfg["cam_vflip"] = 1 if "cam_vflip" in fields else 0
    cfg["cam_hmirror"] = 1 if "cam_hmirror" in fields else 0
    cfg["cam_speffect"] = int(fields.get("cam_speffect", cfg.get("cam_speffect", 0)))
    cfg["cam_stream_port"] = int(
        fields.get("cam_stream_port", cfg.get("cam_stream_port", 8081))
    )

    save_config(cfg)

    # Trigger camera reconfiguration with new settings
    if camera_available:
        try:
            reconfigure_camera()
        except Exception as e:
            print(f"Camera reconfiguration failed: {e}")

    return cfg, "/admin"


def handle_get():
    cfg = load_config()
    html = build_admin_page(cfg)
    return "200 OK", "text/html", html


def _valid_vehicle_types():
    """Return set of valid vehicle type names"""
    return {t["typeName"] for t in VEHICLE_TYPES}


def build_admin_page(cfg):
    """Build the admin page HTML with current configuration"""
    try:
        # Use template caching - import here to avoid circular import
        from web.web_server import _load_template

        # Load header navigation
        header_nav = _load_template("web/pages/assets/header_nav.html")
        if not header_nav:
            header_nav = "<div>Header not found</div>"
        header_nav = header_nav.replace(
            "{{ vehicle_name }}", cfg.get("vehicleName", "") or ""
        )

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
            ("5", "CIF (400x296)"),
            ("6", "VGA (640x480)"),
            ("7", "SVGA (800x600)"),
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

        replacements = {
            "{{ header_nav }}": header_nav,
            "{{ type_options }}": type_options,
            "{{ vehicle_tag }}": cfg.get("vehicleTag", "") or "",
            "{{ vehicle_name }}": cfg.get("vehicleName", "") or "",
            "{{ framesize_options }}": framesize_options_html,
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
            "{{vehicle_type_map}}": vehicle_type_js,
        }

        for placeholder, value in replacements.items():
            html = html.replace(placeholder, value)

        return html

    except Exception as e:
        print(f"Error building admin page: {e}")
        return f"<html><body><h2>Error loading admin page: {e}</h2></body></html>"
