"""
Shared API Handler for RokCommon

This module provides a unified API handler that can be used by both
RokVehicle and RokVision projects to handle common API endpoints.

Endpoints:
- /api/status - Device status information
- /api/restart - Device restart

Project-specific extensions can be added via callbacks.
"""

import gc
from .request_response import Request, Response
from ..variables.vars_store import get_config_value

# ESP32 support for temperature and restart
try:
    import esp32

    esp32_available = True
except ImportError:
    esp32 = None
    esp32_available = False

try:
    import machine

    machine_available = True
except ImportError:
    machine = None
    machine_available = False


class APIHandler:
    """
    Shared API handler for common endpoints
    """

    def __init__(self, status_callback=None, custom_endpoints=None):
        """
        Initialize API handler

        Args:
            status_callback: Optional callback to extend status response
            custom_endpoints: Dict of additional API endpoints
        """
        self.status_callback = status_callback
        self.custom_endpoints = custom_endpoints or {}

    async def handle(self, request):
        """
        Route API requests to appropriate handlers

        Args:
            request: Request object from unified system

        Returns:
            HTTP response string
        """
        path = request.path
        method = request.method

        try:
            # Remove /api prefix
            api_path = path[4:]  # Remove "/api"

            # Route to handlers
            if api_path == "/status":
                return await self._handle_status(request)
            elif api_path == "/restart" and method == "POST":
                return await self._handle_restart(request)
            elif api_path in self.custom_endpoints:
                # Call custom endpoint handler
                handler = self.custom_endpoints[api_path]
                return await handler(request)
            else:
                return self._json_response(
                    {"error": f"API endpoint {api_path} not found"},
                    status="404 Not Found",
                )

        except Exception as e:
            print(f"API error: {e}")
            return self._json_response(
                {"error": f"API error: {e}"}, status="500 Internal Server Error"
            )

    async def _handle_status(self, request):
        """Handle /api/status endpoint"""
        try:
            # Get basic system info
            mcu_temp = None
            if esp32_available:
                try:
                    if hasattr(esp32, "mcu_temperature"):
                        mcu_temp = esp32.mcu_temperature()
                    elif hasattr(esp32, "raw_temperature"):
                        mcu_temp = esp32.raw_temperature()
                except Exception:
                    pass

            # Get project type from config
            project_type = get_config_value("projectType", "unknown")

            # Build base status response
            status_info = {
                "vehicleName": get_config_value("vehicleName", "Unnamed Device"),
                "tag": get_config_value("vehicleTag", "N/A"),
                "type": get_config_value("vehicleType", "Unknown"),
                "vehicleType": get_config_value("vehicleType", "Unknown"),
                "project": project_type,
                "battery": None,  # Project-specific
                "mcu_temp": mcu_temp,
                "memory": {"free": gc.mem_free(), "allocated": gc.mem_alloc()},
            }

            # Add vehicle-specific busy status if this is a vehicle project
            if project_type == "vehicle":
                try:
                    # Import here to avoid circular imports
                    from web.web_server import WS_CLIENT

                    status_info["busy"] = bool(WS_CLIENT)
                except Exception:
                    status_info["busy"] = False

            # Call project-specific status callback if provided (for additional data)
            if self.status_callback:
                try:
                    additional_status = await self.status_callback(status_info)
                    if additional_status and isinstance(additional_status, dict):
                        status_info.update(additional_status)
                except Exception as e:
                    print(f"Status callback error: {e}")

            return self._json_response(status_info)

        except Exception as e:
            return self._json_response(
                {"error": f"Status error: {e}"}, status="500 Internal Server Error"
            )

    async def _handle_restart(self, request):
        """Handle /api/restart endpoint"""
        try:
            if not machine_available:
                return self._json_response(
                    {"error": "Machine module not available"},
                    status="500 Internal Server Error",
                )

            # Schedule restart after response
            import uasyncio as asyncio

            async def delayed_restart():
                await asyncio.sleep(1)  # Give time for response to send
                machine.reset()

            asyncio.create_task(delayed_restart())

            return self._json_response(
                {"success": True, "message": "Device will restart in 1 second"}
            )

        except Exception as e:
            return self._json_response(
                {"error": f"Restart error: {e}"}, status="500 Internal Server Error"
            )

    def _json_response(self, data, status="200 OK"):
        """Create a JSON HTTP response"""
        try:
            import json

            json_data = json.dumps(data)
            response = (
                f"HTTP/1.1 {status}\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(json_data)}\r\n"
                f"Access-Control-Allow-Origin: *\r\n"
                f"Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
                f"Access-Control-Allow-Headers: Content-Type\r\n"
                f"\r\n"
                f"{json_data}"
            )
            return response
        except Exception as e:
            error_msg = f'{{"error":"JSON serialization error: {e}"}}'
            return (
                f"HTTP/1.1 500 Internal Server Error\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(error_msg)}\r\n"
                f"\r\n"
                f"{error_msg}"
            )


# Convenience function for creating API handler
def create_api_handler(status_callback=None, custom_endpoints=None):
    """Create a shared API handler instance"""
    return APIHandler(status_callback, custom_endpoints)
