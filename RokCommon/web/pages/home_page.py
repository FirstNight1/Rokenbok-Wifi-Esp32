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
        # Get basic device information
        vehicle_name = get_config_value("vehicleName", "Unnamed Device")
        device_type = get_config_value("vehicleType", "Unknown")
        project_type = get_config_value("projectType", "unknown")

        # Get network information
        ip = self._get_ip_address()

        # Get memory information (simple format)
        free_mem = gc.mem_free()
        memory_info = f"{round(free_mem / 1024)} KB free"

        # Load templates
        header_nav = self._load_asset_template("header_nav.html")
        html_content = self._load_asset_template("home_page.html")

        # Process header nav - include project type for navigation links
        header_nav = header_nav.replace("{{ vehicle_name }}", vehicle_name)

        # Set project-specific navigation elements
        if project_type == "vehicle":
            testing_label = "Motor Config"
            play_link = '<a href="/play">Play</a>'
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
            testing_label = "Stream Testing"
            play_link = ""
            busy_status_script = """
            // Vision device - no WebSocket, always ready
            document.getElementById('vehicle_status').textContent = 'Device is ready';
            document.getElementById('vehicle_status').style.color = '#28a745';"""

        header_nav = header_nav.replace("{{ testing_label }}", testing_label)
        header_nav = header_nav.replace("{{ play_link }}", play_link)

        # Prepare template replacements
        replacements = {
            "{{ header_nav }}": header_nav,
            "{{ vehicle_name }}": vehicle_name,
            "{{ device_type }}": device_type,
            "{{ ip }}": ip,
            "{{ memory_info }}": memory_info,
            "{{ busy_status_script }}": busy_status_script,
        }

        for placeholder, value in replacements.items():
            html_content = html_content.replace(placeholder, value)

        # Trigger garbage collection for cleaner memory reading
        gc.collect()

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
        """Load template from RokCommon assets directory"""
        return load_template(f"RokCommon/web/pages/assets/{filename}")


# Unified home handler - no project-specific content injection
home_handler = HomePageHandler()
