from variables.vars_store import load_config, save_config
from variables.vehicle_types import VEHICLE_TYPES
try:
    from control.power_manager import power_manager
except Exception:
    power_manager = None


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
    sleep_state = 'Asleep' if (power_manager and power_manager.is_asleep()) else 'Awake'
    sleep_btn = ''
    if power_manager:
        if power_manager.is_asleep():
            sleep_btn = '<form method="POST" action="/admin"><button type="submit" name="wake" value="1">Wake Vehicle</button></form>'
        else:
            sleep_btn = '<form method="POST" action="/admin"><button type="submit" name="sleep" value="1">Shutdown / Sleep</button></form>'

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

    # Password change section (message injected if present)
    msg = cfg.get('_admin_msg', '')
    msg_html = f"<div style='color:red;margin-bottom:8px'>{msg}</div>" if msg else ''
    return f"""
    <html>
    <body>
    {header_nav}
    <div style='max-width:600px;margin:32px auto 0 auto;'>
        <h2>Admin Settings</h2>
        <div style='margin-bottom:16px;'>
            <b>Vehicle Power State:</b> <span style='color:#1976d2'>{sleep_state}</span><br>
            {sleep_btn}
        </div>
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
        <hr style='margin:32px 0 24px 0'>
        <h3>Change Admin Username/Password</h3>
        {msg_html}
        <form method="POST" action="/admin">
            <input type="hidden" name="change_admin" value="1">
            <label>Current Password:</label><br>
            <input name="current_pw" type="password" maxlength="64"><br><br>
            <label>New Username:</label><br>
            <input name="new_user" maxlength="32" value="{cfg.get('admin_user','admin')}"><br><br>
            <label>New Password:</label><br>
            <input name="new_pw" type="password" maxlength="64"><br><br>
            <label>Confirm New Password:</label><br>
            <input name="confirm_pw" type="password" maxlength="64"><br><br>
            <button type="submit">Change Admin Credentials</button>
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
    # Remove transient message after displaying
    html = build_admin_page(cfg)
    if '_admin_msg' in cfg:
        del cfg['_admin_msg']
        save_config(cfg)
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

    # Handle admin username/password change
    if fields.get('change_admin') == '1':
        from variables.vars_store import check_password, encrypt_password
        import re
        current_pw = fields.get('current_pw','').strip()
        new_user = fields.get('new_user','').strip()
        new_pw = fields.get('new_pw','').strip()
        confirm_pw = fields.get('confirm_pw','').strip()
        # Sanitize username
        new_user = re.sub(r'[^a-zA-Z0-9_\-]','',new_user)[:32]
        # Validate current password
        if not check_password(current_pw, cfg.get('admin_pass','')):
            cfg['_admin_msg'] = 'Current password is incorrect.'
            return cfg, '/admin'
        # Validate new username
        if not new_user or len(new_user) < 3:
            cfg['_admin_msg'] = 'Username must be at least 3 characters.'
            return cfg, '/admin'
        # Validate new password
        if len(new_pw) < 6:
            cfg['_admin_msg'] = 'New password must be at least 6 characters.'
            return cfg, '/admin'
        if new_pw != confirm_pw:
            cfg['_admin_msg'] = 'New passwords do not match.'
            return cfg, '/admin'
        # All good, update config
        cfg['admin_user'] = new_user
        cfg['admin_pass'] = encrypt_password(new_pw)
        cfg['_admin_msg'] = '<span style="color:green">Admin username/password updated successfully.</span>'
        save_config(cfg)
        return cfg, '/admin'

    # Sleep/wake controls
    if power_manager:
        if "sleep" in fields:
            power_manager.shutdown()
            return cfg, "/admin"
        if "wake" in fields:
            power_manager.wake()
            return cfg, "/admin"

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
