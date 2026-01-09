def handle_post(body, cfg):
    """
    body = raw POST body (string)
    cfg  = dict from load_config() passed in by web_server
    """
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

    # ---- HANDLE LED SETTINGS ----
    led_enabled = "ledEnabled" in fields
    led_pin = fields.get("ledPin", "9")

    # Validate LED pin
    try:
        led_pin_num = int(led_pin)
        if led_pin_num not in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 43, 44]:
            led_pin_num = 9  # Default fallback
    except:
        led_pin_num = 9

    # Update LED config
    cfg["ledEnabled"] = led_enabled
    cfg["ledPin"] = led_pin_num

    # Apply LED settings if changed
    from control.led_status import get_led_manager, init_led_status, set_wifi_status

    led_manager = get_led_manager()
    if led_manager:
        # Check if pin changed
        old_pin = getattr(led_manager, "led_pin_num", 9)
        if old_pin != led_pin_num:
            # Reinitialize LED with new pin
            led_manager.deinit()
            led_manager.led_pin_num = led_pin_num
            led_manager.reinit_with_pin(led_pin_num)

        # Set override based on enabled state
        if not led_enabled:
            led_manager.set_override(True, False)  # Force off
        else:
            led_manager.set_override(False)  # Auto mode
            set_wifi_status()  # Update to current WiFi status

    # ---- VALIDATE VEHICLE TYPE ----
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

    # If tag starts with old_tag_prefix + '-', update to new_tag_prefix + '-...'
    if old_tag.startswith(old_tag_prefix + "-"):
        suffix = old_tag[len(old_tag_prefix) + 1 :]
        new_tag = new_tag_prefix + "-" + suffix
    else:
        new_tag = old_tag

    # If user manually changed vehicleTag, use their value
    tag_from_form = fields.get("vehicleTag")
    if tag_from_form is not None and tag_from_form != old_tag:
        new_tag = tag_from_form

    cfg["vehicleType"] = new_type
    cfg["vehicleTag"] = new_tag
    cfg["vehicleName"] = fields.get("vehicleName", cfg.get("vehicleName"))

    save_config(cfg)

    return cfg, "/admin"


def handle_get():
    cfg = load_config()
    html = build_admin_page(cfg)
    return "200 OK", "text/html", html


from variables.vars_store import load_config, save_config
from RokCommon.variables.vehicle_types import VEHICLE_TYPES


# ---------------------------------------------------------
# Utilities
# ---------------------------------------------------------


def _valid_vehicle_types():
    """Return a set of all valid vehicle type names."""
    return {t["typeName"] for t in VEHICLE_TYPES}


def _get_used_motor_pins(cfg):
    """Get a set of pins currently used by motors"""
    used_pins = set()
    try:
        # Import motor pin map and controller
        from control.motor_controller import MOTOR_PIN_MAP, motor_controller

        # Get current motor assignments
        motor_info = motor_controller.get_motor_assignments()
        # Collect pins from all assigned motors
        for motor_name, info in motor_info.items():
            pins = info.get("pins", (None, None))
            if pins[0] is not None:
                used_pins.add(pins[0])
            if pins[1] is not None:
                used_pins.add(pins[1])
    except Exception as e:
        print(f"Error getting used motor pins: {e}")
    return used_pins


# ---------------------------------------------------------
# HTML Builder
# ---------------------------------------------------------


def build_admin_page(cfg):
    # Build dropdown for vehicle types using typeFriendlyName

    # Build dropdown for vehicle types as a single line, no extra whitespace
    type_options = "".join(
        f"<option value='{t['typeName']}'{' selected' if cfg.get('vehicleType')==t['typeName'] else ''}>{t.get('typeFriendlyName', t['typeName'])}</option>"
        for t in VEHICLE_TYPES
    )
    type_options = type_options.replace("\n", "").replace("\r", "").replace("  ", " ")

    # Build JSON mapping of typeName -> tagName for dynamic tag updates, single line
    import json

    vehicle_type_map = json.dumps(
        {t["typeName"]: t["tagName"] for t in VEHICLE_TYPES}, separators=(",", ":")
    )

    # Get current LED settings
    led_enabled = cfg.get("ledEnabled", True)
    led_pin = cfg.get("ledPin", 9)

    # Get motor pin usage to grey out occupied pins
    used_pins = _get_used_motor_pins(cfg)

    # Build LED pin dropdown
    # Use D0-D10, D6, D7 labels for pins 1-10, 43, 44, in requested order
    pin_labels = {
        1: "D0",
        2: "D1",
        3: "D2",
        4: "D3",
        5: "D4",
        6: "D5",
        43: "D6",
        44: "D7",
        7: "D8",
        8: "D9",
        9: "D10",
        10: "D11",
    }
    available_pins = [1, 2, 3, 4, 5, 6, 43, 44, 7, 8, 9, 10]
    led_pin_options = ""
    for pin in available_pins:
        disabled = "disabled" if pin in used_pins else ""
        selected = "selected" if pin == led_pin else ""
        label = pin_labels.get(pin, f"D{pin}") + (
            " (Motor Used)" if pin in used_pins else ""
        )
        led_pin_options += (
            f"<option value='{pin}' {selected} {disabled}>{label}</option>"
        )

    vehicle_tag = cfg.get("vehicleTag") or ""
    vehicle_name = (
        cfg.get("vehicleName") or ""
    )  # Use template caching from web_server module
    try:
        from web.web_server import _load_template
        import gc

        header_nav = _load_template("web/pages/assets/header_nav.html")
        if not header_nav:
            header_nav = f"<div style='background:#222;color:#fff;padding:12px;text-align:center'>Rokenbok Vehicle Control<br><span style='color:#f9e79f'>{vehicle_name}</span></div>"
        else:
            header_nav = header_nav.replace("{{ vehicle_name }}", vehicle_name)

        html = _load_template("web/pages/assets/admin_page.html")
        if html:
            # Ensure all template replacements are single-line and whitespace-free
            html = html.replace(
                "{{ header_nav }}", header_nav.strip().replace("\n", "")
            )
            html = html.replace("{{ type_option }}", type_options.strip())
            html = html.replace("{{ vehicle_tag }}", vehicle_tag.strip())
            html = html.replace("{{ vehicle_name }}", vehicle_name.strip())
            html = html.replace("{{vehicle_type_map}}", vehicle_type_map.strip())
            html = html.replace("{{ led_status }}", "")  # Remove LED status display
            html = html.replace(
                "{{ led_enabled_checked }}", "checked" if led_enabled else ""
            )
            html = html.replace("{{ led_pin_options }}", led_pin_options.strip())
        else:
            html = (
                f"<html><body><h2>Error loading admin page template</h2></body></html>"
            )

        # Cleanup for GC
        gc.collect()
        return html

    except Exception as e:
        print(f"Admin page template error: {e}")
        return f"<html><body><h2>Admin template error: {e}</h2></body></html>"
