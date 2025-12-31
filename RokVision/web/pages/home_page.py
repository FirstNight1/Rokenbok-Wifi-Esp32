# web/pages/home_page.py

from variables.vars_store import load_config
import network
import gc


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


def get_memory_info():
    """Get current memory allocation info."""
    try:
        # Trigger garbage collection to get accurate reading
        gc.collect()
        free = gc.mem_free()
        allocated = gc.mem_alloc()
        total = free + allocated
        usage_percent = round((allocated / total) * 100, 1)

        return {
            "free": free,
            "allocated": allocated,
            "total": total,
            "usage_percent": usage_percent,
        }
    except Exception:
        return {
            "free": "N/A",
            "allocated": "N/A",
            "total": "N/A",
            "usage_percent": "N/A",
        }


def render_home_page():
    """Generate HTML for the home page."""

    try:
        ip = get_ip_address()
        cfg = load_config()
        port = cfg.get("cam_stream_port", 8081)
        stream_url = f"http://{ip}:{port}/stream"

        # Get memory info
        mem_info = get_memory_info()
    except Exception as e:
        print(f"Error getting network/config info: {e}")
        ip = "Error"
        stream_url = "Error"
        mem_info = get_memory_info()  # Still try to get memory info

    # Use template caching - import here to avoid circular import
    from web.web_server import _load_template

    # Load header/nav HTML and inject vehicle_name (placeholder, will update via JS)
    try:
        header_nav = _load_template("web/pages/assets/header_nav.html")
        if header_nav:
            header_nav = header_nav.replace("{{ vehicle_name }}", "Loading...")
        else:
            raise Exception("Template not found")
    except Exception as e:
        print(f"Error loading header_nav.html: {e}")
        header_nav = "<div style='background:#222;color:#fff;padding:12px;text-align:center'>Header unavailable</div>"

    try:
        html = _load_template("web/pages/assets/home_page.html")
        if not html:
            raise Exception("Template not found")
    except Exception as e:
        print(f"Error loading home_page.html: {e}")
        html = "<html><body><h2>Home page asset missing</h2></body></html>"

    try:
        html = html.replace("{{ header_nav }}", header_nav)
        html = html.replace("{{ ip }}", str(ip))
        html = html.replace("{{ stream_url }}", str(stream_url))

        # Add memory info replacements
        html = html.replace("{{ mem_free }}", str(mem_info["free"]))
        html = html.replace("{{ mem_allocated }}", str(mem_info["allocated"]))
        html = html.replace("{{ mem_total }}", str(mem_info["total"]))
        html = html.replace("{{ mem_usage_percent }}", str(mem_info["usage_percent"]))
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
