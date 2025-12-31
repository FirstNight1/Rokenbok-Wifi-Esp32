# web/pages/home_page.py

from variables.vars_store import load_config
import network
import gc


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
    """Generate HTML for the home page with improved performance."""
    ip = get_ip_address()

    # Get current memory info
    free_mem = gc.mem_free()
    mem_info = f"{round(free_mem / 1024)} KB free"

    # Use template caching from web_server module
    try:
        from web.web_server import _load_template

        header_nav = _load_template("web/pages/assets/header_nav.html")
        if not header_nav:
            header_nav = "<div style='background:#222;color:#fff;padding:12px;text-align:center'>Rokenbok Vehicle Control<br><span style='color:#f9e79f'>Loading...</span></div>"
        else:
            header_nav = header_nav.replace("{{ vehicle_name }}", "Loading...")

        html = _load_template("web/pages/assets/home_page.html")
        if not html:
            html = "<html><body><h2>Home page asset missing</h2></body></html>"
        else:
            html = html.replace("{{ header_nav }}", header_nav)
            html = html.replace("{{ ip }}", ip)
            html = html.replace("{{ memory_info }}", mem_info)
    except Exception as e:
        print("[ERROR] Failed to load home page templates:", e)
        html = f"<html><body><h2>Template error: {e}</h2><p><a href='/admin'>Admin</a></p></body></html>"

    # Explicit cleanup to help GC
    gc.collect()
    return html


def handle_get():
    """Return (status, content_type, html) for async web server."""
    html = render_home_page()
    return ("200 OK", "text/html", html)
