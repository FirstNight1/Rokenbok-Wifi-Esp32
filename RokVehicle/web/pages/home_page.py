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

    print("[DEBUG] Entered render_home_page")
    ip = get_ip_address()
    print("[DEBUG] Got IP:", ip)
    # Load header/nav HTML and inject vehicle_name (placeholder, will update via JS)
    try:
        print("[DEBUG] Opening header_nav.html")
        with open("web/pages/assets/header_nav.html", "r") as f:
            header_nav = f.read().replace("{{ vehicle_name }}", "Loading...")
        print("[DEBUG] Loaded header_nav.html")
    except Exception as e:
        print("[ERROR] Failed to load header_nav.html:", e)
        header_nav = "<div style='background:#222;color:#fff;padding:12px;text-align:center'>Rokenbok Vehicle Control<br><span style='color:#f9e79f'>Loading...</span></div>"

    try:
        print("[DEBUG] Opening home_page.html")
        with open("web/pages/assets/home_page.html", "r") as f:
            html = f.read()
        print("[DEBUG] Loaded home_page.html")
    except Exception as e:
        print("[ERROR] Failed to load home_page.html:", e)
        html = "<html><body><h2>Home page asset missing</h2></body></html>"

    html = html.replace("{{ header_nav }}", header_nav)
    html = html.replace("{{ ip }}", ip)
    print("[DEBUG] Returning home page HTML")
    return html


def handle_get():
    """Return (status, content_type, html) for async web server."""
    html = render_home_page()
    return ("200 OK", "text/html", html)
