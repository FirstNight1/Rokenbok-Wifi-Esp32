"""
WiFi Configuration Page Handler for RokCommon

This module provides a unified WiFi configuration page that can be used by both
RokVehicle and RokVision projects.

Features:
- WiFi network configuration
- DHCP/Static IP configuration
- Network status display
- Template-based rendering using PageHandler methodology
"""

from ..request_response import Request, Response, PageHandler
from ...variables.vars_store import (
    get_config_value,
    save_config_value,
)
from .home_page import load_and_process_header

try:
    import network

    network_available = True
except Exception:
    network = None
    network_available = False


class WiFiPageHandler(PageHandler):
    """
    WiFi configuration page handler using unified Request/Response system
    """

    def handle_get(self, request):
        """Handle GET requests for WiFi configuration page"""
        try:
            # Determine WiFi status
            status_info = {"mode": "ap"}
            if network_available:
                try:
                    sta = network.WLAN(network.STA_IF)
                    if sta.active() and sta.isconnected():
                        status_info = {"connected": True, "ssid": sta.config("essid")}
                    else:
                        status_info = {
                            "connected": False,
                            "ssid": get_config_value("ssid", ""),
                        }
                except Exception:
                    pass

            html = self._build_wifi_page(status_info=status_info)
            return Response.html(html)

        except Exception as e:
            print(f"WiFi page GET error: {e}")
            return Response.server_error(f"WiFi page error: {e}")

    def handle_post(self, request):
        """Handle POST requests for WiFi configuration"""
        try:
            # Parse form data
            form_data = request.get_form_data()

            ssid = form_data.get("ssid", "")
            wifipass = form_data.get("wifipass", "")
            ip_mode = form_data.get("ip_mode", "dhcp")
            static_ip = form_data.get("static_ip", "")
            static_mask = form_data.get("static_mask", "")
            static_gw = form_data.get("static_gw", "")
            static_dns = form_data.get("static_dns", "")

            # Update configuration
            save_config_value("ssid", ssid)
            save_config_value("wifipass", wifipass)
            save_config_value("ip_mode", ip_mode)
            save_config_value("static_ip", static_ip)
            save_config_value("static_mask", static_mask)
            save_config_value("static_gw", static_gw)
            save_config_value("static_dns", static_dns)

            # Clear old failure marker
            save_config_value("wifi_error", None)

            # Redirect to WiFi page
            return Response.redirect("/wifi")

        except Exception as e:
            print(f"WiFi page POST error: {e}")
            return Response.server_error(f"WiFi configuration error: {e}")

    def _build_wifi_page(self, status_info=None):
        """Build WiFi configuration page HTML"""
        # Get configuration values
        ssid_val = get_config_value("ssid", "")
        vehicle_name = get_config_value("vehicleName", "Unnamed Device")
        wifipass = get_config_value("wifipass", "")

        # DHCP/static IP config
        ip_mode = get_config_value("ip_mode", "dhcp")
        static_ip = get_config_value("static_ip", "")
        static_mask = get_config_value("static_mask", "")
        static_gw = get_config_value("static_gw", "")
        static_dns = get_config_value("static_dns", "")

        # Error message handling
        error_msg = ""
        if get_config_value("wifi_error"):
            error_msg = "<p style='color:red'>Error: Unable to connect using the saved WiFi credentials.</p>"

        # Status bar logic
        status_html = ""
        if status_info:
            if status_info.get("mode") == "ap":
                status_html = "<div style='background:#f9e79f;color:#333;padding:8px 0 8px 0;margin-bottom:12px;border-radius:6px;font-weight:bold;'>AP Mode (no WiFi network configured)</div>"
            elif status_info.get("connected"):
                status_html = f"<div style='background:#c8e6c9;color:#256029;padding:8px 0 8px 0;margin-bottom:12px;border-radius:6px;font-weight:bold;'>Connected to: {status_info.get('ssid','?')}</div>"
            else:
                status_html = f"<div style='background:#ffcdd2;color:#b71c1c;padding:8px 0 8px 0;margin-bottom:12px;border-radius:6px;font-weight:bold;'>Not connected to WiFi</div>"

        # Load WiFi page HTML template with error checking
        html_content = self._load_asset_template("wifi_page.html")
        header_nav = load_and_process_header(vehicle_name)

        # Ensure we have valid templates
        if html_content is None or header_nav is None:
            print(
                f"WiFi template loading failed: html_content={html_content is not None}, header_nav={header_nav is not None}"
            )
            return "<html><body><h1>WiFi Template Loading Error</h1><p>Failed to load page templates</p></body></html>"

        # Prepare template replacements with safe string conversion
        static_fields_display = "" if ip_mode == "static" else "display:none;"

        # Replace all template variables
        replacements = {
            "{{ header_nav }}": header_nav or "",
            "{{ status_html }}": status_html or "",
            "{{ error_msg }}": error_msg or "",
            "{{ ssid_val }}": ssid_val or "",
            "{{ vehicle_name }}": vehicle_name or "Unknown Device",
            "{{ dhcp_checked }}": "checked" if ip_mode == "dhcp" else "",
            "{{ static_checked }}": "checked" if ip_mode == "static" else "",
            "{{ static_fields_display }}": static_fields_display or "",
            "{{ static_ip }}": static_ip or "",
            "{{ static_mask }}": static_mask or "",
            "{{ static_gw }}": static_gw or "",
            "{{ static_dns }}": static_dns or "",
            "{{ scan_modal }}": "",  # Scan functionality removed for simplicity
        }

        for placeholder, value in replacements.items():
            if html_content and value is not None:  # Only replace if both are valid
                html_content = html_content.replace(placeholder, str(value))

        return html_content

    def _load_asset_template(self, filename):
        """Load template from RokCommon assets directory with fallback"""
        from ..static_assets import load_template

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
<a href="/">Home</a> | <a href="/wifi">WiFi</a> | <a href="/admin">Admin</a> | <a href="/testing">Testing</a> | <a href="/ota">OTA</a>
</nav>
</header>"""
        elif filename == "wifi_page.html":
            return """<!DOCTYPE html>
<html>
<head><title>WiFi Configuration - {{ vehicle_name }}</title></head>
<body>
{{ header_nav }}
<h2>WiFi Configuration</h2>
{{ status_html }}
{{ error_msg }}
<form method="post" action="/wifi">
<label>SSID: <input type="text" name="ssid" value="{{ ssid_val }}"></label><br><br>
<label>Password: <input type="password" name="wifipass"></label><br><br>
<label><input type="radio" name="ip_mode" value="dhcp" {{ dhcp_checked }}> DHCP</label><br>
<label><input type="radio" name="ip_mode" value="static" {{ static_checked }}> Static IP</label><br><br>
<div style="{{ static_fields_display }}">
<label>Static IP: <input type="text" name="static_ip" value="{{ static_ip }}"></label><br>
<label>Netmask: <input type="text" name="static_mask" value="{{ static_mask }}"></label><br>
<label>Gateway: <input type="text" name="static_gw" value="{{ static_gw }}"></label><br>
<label>DNS: <input type="text" name="static_dns" value="{{ static_dns }}"></label><br>
</div>
<br><button type="submit">Save Configuration</button>
</form>
</body>
</html>"""
        else:
            return f"<html><body><h1>Template not found: {filename}</h1></body></html>"


# Create the handler instance
wifi_handler = WiFiPageHandler()
