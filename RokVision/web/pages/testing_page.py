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
                return Response(status=status, content_type=content_type, body=html)
            else:
                return Response.html(str(result))
        except Exception as e:
            print(f"Testing page GET error: {e}")
            return Response.server_error(f"Testing page error: {e}")

    def handle_post(self, request):
        """Handle POST requests for testing page (if any)"""
        return Response.redirect_to("/testing")


# Create handler instance
testing_handler = TestingPageHandler()


def handle_get_legacy():
    # Load header/nav HTML and inject vehicle_name
    vehicle_name = get_config_value("vehicleName", "")
    
    # Load header navigation using shared function
    header_nav = load_and_process_header(vehicle_name)
    
    # Load template directly
    from RokCommon.web.static_assets import load_template
    html = load_template("web/pages/assets/testing_page.html")
    
    # Replace template placeholders
    html = html.replace("{{ header_nav }}", header_nav)
    html = html.replace(
        "{{ cam_stream_port }}", str(get_config_value("cam_stream_port", 8081))
    )
    
    return ("200 OK", "text/html", html)


# For backward compatibility
def handle_get():
    """Legacy handle_get for backward compatibility"""
    return handle_get_legacy()


# Make the unified handler accessible
handle_get = testing_handler.handle_get
handle_post = testing_handler.handle_post
