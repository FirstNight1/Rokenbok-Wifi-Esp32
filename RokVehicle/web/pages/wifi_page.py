from variables.vars_store import load_config, save_config


# ---------------------------------------------------------
# HTML Builders
# ---------------------------------------------------------

def build_wifi_page(cfg):
    ssid_val = cfg.get("ssid") or ""
    vehicle_name = cfg.get("vehicleName") or ""

    error_msg = ""
    if cfg.get("wifi_error"):
        error_msg = "<p style='color:red'>Error: Unable to connect using the saved WiFi credentials.</p>"

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
        <h2>WiFi Setup</h2>
        {error_msg}
        <form method="POST" action="/wifi">
            <label>SSID:</label><br>
            <input name="ssid" value="{ssid_val}"><br><br>
            <label>Password:</label><br>
            <input name="wifipass" type="password"><br><br>
            <input type="submit" value="Save">
        </form>
    </div>
    </body>
    </html>
    """


# ---------------------------------------------------------
# GET Handler
# ---------------------------------------------------------

def handle_get():
    cfg = load_config()
    html = build_wifi_page(cfg)
    return "200 OK", "text/html", html


# ---------------------------------------------------------
# POST Handler
# ---------------------------------------------------------

def handle_post(body, cfg):
    """
    body = raw POST body (URL-encoded string)
    cfg  = existing config dict (passed in by web_server)
    """

    # Parse POST fields
    fields = {}
    for pair in body.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            fields[k] = v.replace("+", " ")  # Basic decode

    ssid = fields.get("ssid", "")
    wifipass = fields.get("wifipass", "")

    cfg["ssid"] = ssid
    cfg["wifipass"] = wifipass

    # Clear old failure marker
    cfg.pop("wifi_error", None)

    save_config(cfg)

    # Redirect to GET /wifi
    return cfg, "/wifi"
