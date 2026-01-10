from RokCommon.variables.vars_store import get_config_value
from RokCommon.web.request_response import Request, Response
from RokCommon.web import PageHandler
from RokCommon.web.pages.home_page import load_and_process_header


class TestingPageHandler(PageHandler):
    """Testing page handler using unified Request/Response system"""

    def handle_get(self, request):
        """Handle GET requests for testing page"""
        try:
            result = handle_get_legacy()
            if isinstance(result, tuple) and len(result) == 3:
                status, content_type, html = result
                return Response(200, "OK", html, {"Content-Type": content_type})
            else:
                return Response.html(str(result))
        except Exception as e:
            print(f"Testing page GET error: {e}")
            return Response.server_error(f"Testing page error: {e}")

    def handle_post(self, request):
        """Handle POST requests for testing page (if any)"""
        return Response.redirect("/testing")


# Create handler instance
testing_handler = TestingPageHandler()


def handle_get_legacy():
    # Load header/nav HTML and inject vehicle_name
    vehicle_name = get_config_value("vehicleName", "")
    try:
        # Load header navigation using shared function
        header_nav = load_and_process_header(vehicle_name)
        if not header_nav:
            raise Exception("Header template not found")
    except Exception:
        header_nav = "<div style='background:#222;color:#fff;padding:12px;text-align:center'>Header unavailable</div>"
    try:
        # Load template helper function
        def _load_template(path):
            """Load template with fallback paths"""
            from RokCommon.web.static_assets import load_template

            # For project-specific templates, try relative path first
            if (
                "admin_page.html" in path
                or "testing_page.html" in path
                or "play_page.html" in path
            ):
                content = load_template(path)
                if content is not None:
                    return content
                # Don't try RokCommon path for project-specific templates
                return None

            # For common templates, try RokCommon path first
            content = load_template(f"RokCommon/{path}")
            if content is not None:
                return content
            # Fallback to relative path
            content = load_template(path)
            if content is not None:
                return content
            return None

        html = _load_template("web/pages/assets/testing_page.html")
        if not html:
            raise Exception("Template not found")
        html = html.replace("{{ header_nav }}", header_nav)
        html = html.replace(
            "{{ cam_stream_port }}", str(get_config_value("cam_stream_port", 8081))
        )
    except Exception as e:
        html = f"<html><body><h2>Error loading testing page: {e}</h2></body></html>"
    return ("200 OK", "text/html", html)


# For backward compatibility
def handle_get():
    """Legacy handle_get for backward compatibility"""
    return handle_get_legacy()


# Make the unified handler accessible
handle_get = testing_handler.handle_get
handle_post = testing_handler.handle_post
