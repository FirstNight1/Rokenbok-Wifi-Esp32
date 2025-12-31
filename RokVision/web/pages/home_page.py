# web/pages/home_page.py

from variables.vars_store import load_config
import network


def get_ip_address():
    """Return the active IP address (STA preferred, then AP)."""

    try:
        sta = network.WLAN(network.STA_IF)
        if sta.active() and sta.isconnected():
            return sta.ifconfig()[0]
    except Exception as e:
        print(f"Error accessing STA interface: {e}")

    try:
        ap = network.WLAN(network.AP_IF)
        if ap.active():
            return ap.ifconfig()[0]
    except Exception as e:
        print(f"Error accessing AP interface: {e}")

    return "Unavailable"


def render_home_page():
    """Generate HTML for the home page."""

    try:
        ip = get_ip_address()
        cfg = load_config()
        port = cfg.get("cam_stream_port", 8081)
        stream_url = f"http://{ip}:{port}/stream"
    except Exception as e:
        print(f"Error getting network info: {e}")
        ip = "Error"
        stream_url = "Error"

    # Load header/nav HTML and inject vehicle_name (placeholder, will update via JS)
    try:
        with open("web/pages/assets/header_nav.html", "r") as f:
            header_nav = f.read().replace("{{ vehicle_name }}", "Loading...")
    except Exception as e:
        print(f"Error loading header_nav.html: {e}")
        header_nav = "<div style='background:#222;color:#fff;padding:12px;text-align:center'>Header unavailable</div>"

    try:
        with open("web/pages/assets/home_page.html", "r") as f:
            html = f.read()
    except Exception as e:
        print(f"Error loading home_page.html: {e}")
        html = "<html><body><h2>Home page asset missing</h2></body></html>"

    try:
        html = html.replace("{{ header_nav }}", header_nav)
        html = html.replace("{{ ip }}", str(ip))
        html = html.replace("{{ stream_url }}", str(stream_url))
    except Exception as e:
        print(f"Error processing template: {e}")
        html = "<html><body><h2>Template processing error</h2></body></html>"

    return html


def handle_get():
    """Return (status, content_type, html) for async web server."""
    try:
        html = render_home_page()
        return ("200 OK", "text/html", html)
    except Exception as e:
        print(f"Error in home page handle_get: {e}")
        return (
            "500 Internal Server Error",
            "text/html",
            "<html><body><h2>Home page error</h2></body></html>",
        )
