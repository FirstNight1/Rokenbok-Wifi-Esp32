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
    set_config_value,
    load_config,
    save_config,
)

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
            cfg = load_config()

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
                            "ssid": cfg.get("ssid") or "",
                        }
                except Exception:
                    pass

            html = self._build_wifi_page(cfg, status_info=status_info)
            return Response.html(html)

        except Exception as e:
            print(f"WiFi page GET error: {e}")
            return Response.server_error(f"WiFi page error: {e}")

    def handle_post(self, request):
        """Handle POST requests for WiFi configuration"""
        try:
            cfg = load_config()

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
            cfg["ssid"] = ssid
            cfg["wifipass"] = wifipass
            cfg["ip_mode"] = ip_mode
            cfg["static_ip"] = static_ip
            cfg["static_mask"] = static_mask
            cfg["static_gw"] = static_gw
            cfg["static_dns"] = static_dns

            # Clear old failure marker
            cfg.pop("wifi_error", None)

            save_config(cfg)

            # Redirect to WiFi page
            return Response.redirect("/wifi")

        except Exception as e:
            print(f"WiFi page POST error: {e}")
            return Response.server_error(f"WiFi configuration error: {e}")

    def _build_wifi_page(self, cfg, status_info=None):
        """Build WiFi configuration page HTML"""
        # Get configuration values
        ssid_val = cfg.get("ssid") or ""
        vehicle_name = cfg.get("vehicleName") or "Unnamed Device"
        wifipass = cfg.get("wifipass") or ""

        # DHCP/static IP config
        ip_mode = cfg.get("ip_mode", "dhcp")
        static_ip = cfg.get("static_ip", "")
        static_mask = cfg.get("static_mask", "")
        static_gw = cfg.get("static_gw", "")
        static_dns = cfg.get("static_dns", "")

        # Error message handling
        error_msg = ""
        if cfg.get("wifi_error"):
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

        # Load WiFi page HTML template
        html_content = self._load_asset_template("wifi_page.html")
        header_nav = self._load_asset_template("header_nav.html")

        # Process header nav
        header_nav = header_nav.replace("{{ vehicle_name }}", vehicle_name)

        # Prepare template replacements
        static_fields_display = "" if ip_mode == "static" else "display:none;"

        # Replace all template variables
        replacements = {
            "{{ header_nav }}": header_nav,
            "{{ status_html }}": status_html,
            "{{ error_msg }}": error_msg,
            "{{ ssid_val }}": ssid_val,
            "{{ vehicle_name }}": vehicle_name,
            "{{ dhcp_checked }}": "checked" if ip_mode == "dhcp" else "",
            "{{ static_checked }}": "checked" if ip_mode == "static" else "",
            "{{ static_fields_display }}": static_fields_display,
            "{{ static_ip }}": static_ip,
            "{{ static_mask }}": static_mask,
            "{{ static_gw }}": static_gw,
            "{{ static_dns }}": static_dns,
            "{{ scan_modal }}": "",  # Scan functionality removed for simplicity
        }

        for placeholder, value in replacements.items():
            html_content = html_content.replace(placeholder, value)

        return html_content

    def _load_asset_template(self, filename):
        """Load template from RokCommon assets directory"""
        with open(f"RokCommon/web/pages/assets/{filename}", "r") as f:
            return f.read()


# Create the handler instance
wifi_handler = WiFiPageHandler()
