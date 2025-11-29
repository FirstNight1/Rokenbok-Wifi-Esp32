# web/pages/home_page.py

from variables.vars_store import load_config
import network


def get_ip_address():
    """Return the active IP address (STA preferred, then AP)."""

    sta = network.WLAN(network.STA_IF)
    ap = network.WLAN(network.AP_IF)

    if sta.active() and sta.isconnected():
        return sta.ifconfig()[0]

    if ap.active():
        return ap.ifconfig()[0]

    return "Unavailable"


def render_home_page():
    """Generate HTML for the home page."""

    cfg = load_config()

    vehicle_name = cfg.get("vehicleName", "Unnamed Vehicle")
    vehicle_type = cfg.get("vehicleType", "Unknown")
    ssid = cfg.get("ssid", "(AP Mode)")
    battery = "N/A"  # until ADC wired

    ip = get_ip_address()

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
<div style='max-width:600px;margin:32px auto 0 auto;text-align:center;'>
  <p><b>Vehicle Type:</b> {vehicle_type}</p>
  <p><b>WiFi SSID / Mode:</b> {ssid}</p>
  <p><b>IP Address:</b> {ip}</p>
  <p><b>Battery Level:</b> {battery}</p>
  <button class='play-now-btn' onclick="window.location='/play'">Play Now</button>
</div>
</body>
</html>
"""


def handle_get():
    """Return (status, content_type, html) for async web server."""
    html = render_home_page()
    return ("200 OK", "text/html", html)
