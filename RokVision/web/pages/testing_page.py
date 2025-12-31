from variables.vars_store import load_config


def handle_get():
    cfg = load_config()
    # Load header/nav HTML and inject vehicle_name
    vehicle_name = cfg.get("vehicleName") or ""
    try:
        # Use template caching - import here to avoid circular import
        from web.web_server import _load_template

        header_nav = _load_template("web/pages/assets/header_nav.html")
        if not header_nav:
            raise Exception("Template not found")
        header_nav = header_nav.replace("{{ vehicle_name }}", vehicle_name)
    except Exception:
        header_nav = "<div style='background:#222;color:#fff;padding:12px;text-align:center'>Header unavailable</div>"
    try:
        from web.web_server import _load_template

        html = _load_template("web/pages/assets/testing_page.html")
        if not html:
            raise Exception("Template not found")
        html = html.replace("{{ header_nav }}", header_nav)
        html = html.replace(
            "{{ cam_stream_port }}", str(cfg.get("cam_stream_port", 8081))
        )
    except Exception as e:
        html = f"<html><body><h2>Error loading testing page: {e}</h2></body></html>"
    return ("200 OK", "text/html", html)
