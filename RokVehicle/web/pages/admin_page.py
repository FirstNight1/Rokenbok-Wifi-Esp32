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

    # Build dropdown for vehicle types
    type_options = "".join([
        f"<option value='{t['typeName']}' {'selected' if cfg.get('vehicleType')==t['typeName'] else ''}>{t['typeName']}</option>"
        for t in VEHICLE_TYPES
    ])

    vehicle_tag = cfg.get("vehicleTag") or ""
    vehicle_name = cfg.get("vehicleName") or ""

    # Load header/nav HTML and inject vehicle_name
    try:
        with open("web/pages/assets/header_nav.html", "r") as f:
            header_nav = f.read().replace("{{ vehicle_name }}", vehicle_name)
    except Exception:
        header_nav = f"<div style='background:#222;color:#fff;padding:12px;text-align:center'>Rokenbok Vehicle Control<br><span style='color:#f9e79f'>{vehicle_name}</span></div>"

    return f"""
    <html>
    <body>
    {header_nav}
    <div style='max-width:600px;margin:32px auto 0 auto;'>
        <h2>Admin Settings</h2>
        <form method="POST" action="/admin">
            <label>Vehicle Type:</label><br>
            <select name="vehicleType">{type_options}</select><br><br>
            <label>Vehicle Tag:</label><br>
            <input name="vehicleTag" value="{vehicle_tag}"><br><br>
            <label>Vehicle Name:</label><br>
            <input name="vehicleName" value="{vehicle_name}"><br><br>
            <button type="submit" name="save" value="1">Save</button>
            <button type="submit" name="cancel" value="1">Cancel</button>
        </form>
    </div>
    </body>
    </html>
    """


# ---------------------------------------------------------
# GET Handler (NOW RETURNS 3-TUPLE)
# ---------------------------------------------------------

def handle_get():
    cfg = load_config()
    html = build_admin_page(cfg)
    return "200 OK", "text/html", html


# ---------------------------------------------------------
# POST Handler (NOW MATCHES WEB SERVER API)
# ---------------------------------------------------------

def handle_post(body, cfg):
    """
    body = raw POST body (string)
    cfg  = dict from load_config() passed in by web_server
    """

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
    valid_types = _valid_vehicle_types()

    if new_type not in valid_types:
        print("⚠️ Invalid vehicleType received:", new_type)
        return cfg, "/admin"

    # Update cfg
    cfg["vehicleType"] = new_type
    cfg["vehicleTag"] = fields.get("vehicleTag", cfg.get("vehicleTag"))
    cfg["vehicleName"] = fields.get("vehicleName", cfg.get("vehicleName"))

    save_config(cfg)

    return cfg, "/admin"
