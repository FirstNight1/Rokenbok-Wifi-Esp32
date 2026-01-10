"""
Unified Home Page Handler for RokCommon

This module provides a single, unified home page that works for both
RokVehicle and RokVision projects without project-specific content injection.

Features:
- Device information display
- WebSocket busy status (Vehicle only)
- IP address display
- Memory information
- Navigation via header
"""

from ..request_response import Request, Response, PageHandler
from ...variables.vars_store import get_config_value
from ..static_assets import load_template
import gc

try:
    import network

    network_available = True
except Exception:
    network = None
    network_available = False


class HomePageHandler(PageHandler):
    """
    Unified home page handler - no project-specific content injection
    """

    def __init__(self):
        """Initialize home page handler"""
        pass

    def handle_get(self, request):
        """Handle GET requests for home page"""
        try:
            html = self._render_home_page()
            return Response.html(html)

        except Exception as e:
            print(f"Home page GET error: {e}")
            return Response.server_error(f"Home page error: {e}")

    def _render_home_page(self):
        """Generate HTML for the unified home page"""
        # Get basic device information from config
        vehicle_name = get_config_value("vehicleName", "Unnamed Device")
        device_type = get_config_value("vehicleType", "Unknown")
        project_type = get_config_value("projectType", "unknown")

        # Get network information
        ip = self._get_ip_address()

        # Get memory information
        free_mem = gc.mem_free()
        memory_info = f"{round(free_mem / 1024)} KB free"

        # Load templates
        header_nav = self.load_and_process_header(vehicle_name, project_type)
        html_content = self._load_asset_template("home_page.html")

        # Set project-specific busy status script
        if project_type == "vehicle":
            busy_status_script = """
            // Vehicle has WebSocket busy status
            if (js.busy !== undefined) {
                document.getElementById('vehicle_status').textContent = js.busy ? 'Vehicle is busy' : 'Vehicle is ready';
                document.getElementById('vehicle_status').style.color = js.busy ? '#dc3545' : '#28a745';
            } else {
                document.getElementById('vehicle_status').textContent = 'Vehicle is ready';
                document.getElementById('vehicle_status').style.color = '#28a745';
            }"""
        else:
            busy_status_script = """
            // Vision device - no WebSocket, always ready
            document.getElementById('vehicle_status').textContent = 'Device is ready';
            document.getElementById('vehicle_status').style.color = '#28a745';"""

        # Simple template replacements
        replacements = {
            "{{ header_nav }}": header_nav,
            "{{ vehicle_name }}": vehicle_name,
            "{{ device_type }}": device_type,
            "{{ ip }}": ip,
            "{{ memory_info }}": memory_info,
            "{{ busy_status_script }}": busy_status_script,
        }

        for placeholder, value in replacements.items():
            html_content = html_content.replace(placeholder, str(value))

        return html_content

    def _get_ip_address(self):
        """Return the active IP address (STA preferred, then AP)"""
        if not network_available:
            return "Network unavailable"

        # Try STA interface first
        sta = network.WLAN(network.STA_IF)
        if sta.active() and sta.isconnected():
            return sta.ifconfig()[0]

        # Fall back to AP interface
        ap = network.WLAN(network.AP_IF)
        if ap.active():
            return ap.ifconfig()[0]

        return "Unavailable"

    def _load_asset_template(self, filename):
        """Load template from RokCommon assets directory with fallback"""
        # Try main path first
        content = load_template(f"RokCommon/web/pages/assets/{filename}")
        if content is not None:
            return content

        # Fallback to relative path
        content = load_template(f"web/pages/assets/{filename}")
        if content is not None:
            return content

        # Final fallback - minimal template
        if filename == "header_nav.html":
            return """<header>
<h1>{{ vehicle_name }}</h1>
<nav>
<a href="/">Home</a> | <a href="/wifi">WiFi</a> | <a href="/admin">Admin</a> | <a href="/testing">{{ testing_label }}</a> | <a href="/ota">OTA</a>
{{ play_link }}
</nav>
</header>"""
        elif filename == "home_page.html":
            return """<!DOCTYPE html>
<html>
<head><title>{{ vehicle_name }}</title></head>
<body>
{{ header_nav }}
<h2>Device Information</h2>
<p>Type: {{ device_type }}</p>
<p>IP: {{ ip }}</p>
<p>Memory: {{ memory_info }}</p>
<p id="vehicle_status">Loading...</p>
<script>{{ busy_status_script }}</script>
</body>
</html>"""
        else:
            return f"<html><body><h1>Template not found: {filename}</h1></body></html>"

    def process_header_nav(self, header_nav, vehicle_name=None, project_type=None):
        """
        Process header navigation template with project-specific elements.
        This is a shared function that all pages should use for consistent header handling.
        """
        if not header_nav:
            return ""

        # Use passed values or get defaults
        if vehicle_name is None:
            vehicle_name = get_config_value("vehicleName", "Unknown Device")
        if project_type is None:
            project_type = get_config_value("projectType", "unknown")

        # Replace vehicle name
        header_nav = header_nav.replace(
            "{{ vehicle_name }}", vehicle_name or "Unknown Device"
        )

        # Set project-specific navigation elements
        if project_type == "vehicle":
            testing_label = "Motor Config"
            play_link = '<a href="/play">Play</a>'
        else:
            testing_label = "Stream Testing"
            play_link = ""

        # Replace project-specific placeholders
        header_nav = header_nav.replace("{{ testing_label }}", testing_label)
        header_nav = header_nav.replace("{{ play_link }}", play_link)

        return header_nav

    def load_and_process_header(self, vehicle_name=None, project_type=None):
        """
        Load and process header template with fallbacks.
        This is a shared function that all pages should use.
        """
        # Load header template with fallback
        header_nav = self._load_asset_template("header_nav.html")

        # Process with project-specific elements
        return self.process_header_nav(header_nav, vehicle_name, project_type)


# Unified home handler - no project-specific content injection
home_handler = HomePageHandler()


# Global functions for shared header processing that other pages can use
def load_and_process_header(vehicle_name=None, project_type=None):
    """Global function for loading and processing header across all pages"""
    return home_handler.load_and_process_header(vehicle_name, project_type)


def load_header_template(filename="header_nav.html"):
    """Global function for loading header template with fallbacks"""
    return home_handler._load_asset_template(filename)
