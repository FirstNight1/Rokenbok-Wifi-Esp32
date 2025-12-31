from variables.vars_store import load_config


def handle_get():
    cfg = load_config()
    # Load header/nav HTML and inject vehicle_name
    vehicle_name = cfg.get("vehicleName") or ""
    try:
        with open("web/pages/assets/header_nav.html", "r") as f:
            header_nav = f.read().replace("{{ vehicle_name }}", vehicle_name)
    except Exception:
        header_nav = "<div style='background:#222;color:#fff;padding:12px;text-align:center'>Header unavailable</div>"
    try:
        with open("web/pages/assets/testing_page.html", "r") as f:
            html = f.read()
        html = html.replace("{{ header_nav }}", header_nav)
        html = html.replace(
            "{{ cam_stream_port }}", str(cfg.get("cam_stream_port", 8081))
        )
    except Exception as e:
        html = f"<html><body><h2>Error loading testing page: {e}</h2></body></html>"
    return ("200 OK", "text/html", html)
