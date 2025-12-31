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
from variables.vehicle_types import VEHICLE_TYPES


# ---------------------------------------------------------
# Utilities
# ---------------------------------------------------------


def _valid_vehicle_types():
    """Return a set of all valid vehicle type names."""
    return {t["typeName"] for t in VEHICLE_TYPES}


# ---------------------------------------------------------
# HTML Builder
# ---------------------------------------------------------


def build_admin_page(cfg):
    # Build dropdown for vehicle types using typeFriendlyName
    type_options = "".join(
        [
            f"<option value='{t['typeName']}' {'selected' if cfg.get('vehicleType')==t['typeName'] else ''}>{t.get('typeFriendlyName', t['typeName'])}</option>"
            for t in VEHICLE_TYPES
        ]
    )

    # Build JavaScript mapping of typeName -> tagName for dynamic tag updates
    vehicle_type_map = ", ".join(
        [f'"{t["typeName"]}": "{t["tagName"]}"' for t in VEHICLE_TYPES]
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
            html = html.replace("{{ header_nav }}", header_nav)
            html = html.replace("{{ type_options }}", type_options)
            html = html.replace("{{ vehicle_tag }}", vehicle_tag)
            html = html.replace("{{ vehicle_name }}", vehicle_name)
            html = html.replace("{{vehicle_type_map}}", vehicle_type_map)
            html = html.replace("{{ led_status }}", "")  # Remove LED status display
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
