import uasyncio as asyncio
import sys
from web.pages import admin_page, testing_page
from RokCommon.ota.ota_page import ota_handler
from RokCommon.web import handle_request, create_routes_from_modules
from RokCommon.web.pages import wifi_page, home_page
from RokCommon.web.api_handler import create_api_handler
from RokCommon.variables.vars_store import get_config_value
import gc

# Import performance monitoring
try:
    from lib.performance_utils import perf_monitor, memory_pressure_check
except Exception:
    perf_monitor = None
    memory_pressure_check = None

try:
    import esp32
    esp32_available = True
except ImportError:
    esp32 = None
    esp32_available = False

# Template cache to avoid file I/O on every request
_template_cache = {}
_cache_enabled = True

# Create routes using the unified handlers
ROUTES = {
    "/": home_page.home_handler,
    "/wifi": wifi_page.wifi_handler,
    "/admin": admin_page,
    "/testing": testing_page.testing_handler,
    "/ota": ota_handler,  # Multi-step OTA system
}


def _load_template(path):
    """Load template from file with caching"""
    if _cache_enabled and path in _template_cache:
        return _template_cache[path]
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if _cache_enabled:
            _template_cache[path] = content
        
        return content
    except Exception as e:
        print(f"Template load error for {path}: {e}")
        return None


async def handle_client(reader, writer):
    """Client handler with API support and direct page handling"""
    try:
        # Read request line
        req_line = await reader.readline()
        if not req_line:
            await writer.aclose()
            return

        line = req_line.decode().strip()

        # Handle HTTP/2 probes and malformed requests
        if line.startswith("PRI * HTTP/2.0") or not line:
            await writer.aclose()
            return

        # Parse request line
        parts = line.split()
        if len(parts) < 2:
            await writer.aclose()
            return

        method = parts[0]
        full_path = parts[1]
        if "?" in full_path:
            path, query_string = full_path.split("?", 1)
        else:
            path, query_string = full_path, ""

        # Read headers
        headers = {}
        while True:
            hdr = await reader.readline()
            if not hdr or hdr == b"\r\n":
                break
            try:
                line = hdr.decode().strip()
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip().lower()] = v.strip()
            except Exception:
                continue

        # Handle API endpoints
        if path.startswith("/api/"):
            body = ""
            if method == "POST":
                content_length = int(headers.get("content-length", 0))
                if content_length > 0:
                    body_bytes = await reader.read(content_length)
                    body = body_bytes.decode("utf-8") if isinstance(body_bytes, bytes) else str(body_bytes)

            await _handle_api_request(writer, method, headers, path, query_string, body)
            return

        # Handle static assets
        if path.startswith("/assets/") or path == "/favicon.ico":
            await _handle_static_assets(writer, path)
            return

        # Handle legacy status endpoint (redirect to API)
        if path == "/status":
            await _handle_legacy_status(writer)
            return

        # Handle page routes directly
        page_handler = ROUTES.get(path)
        if page_handler:
            # Read body for POST requests
            body = ""
            if method == "POST":
                content_length = int(headers.get("content-length", 0))
                if content_length > 0:
                    body_bytes = await reader.read(content_length)
                    body = body_bytes.decode("utf-8") if isinstance(body_bytes, bytes) else str(body_bytes)

            # Create Request object
            from RokCommon.web.request_response import Request, Response
            request = Request(
                method=method,
                path=path,
                query_string=query_string,
                body=body,
                headers=headers,
                content_type=headers.get("content-type", ""),
            )

            # Call the handler directly
            if hasattr(page_handler, 'handle_get') and method == 'GET':
                response = page_handler.handle_get(request)
            elif hasattr(page_handler, 'handle_post') and method == 'POST':
                response = page_handler.handle_post(request)
            elif hasattr(page_handler, '__call__'):
                response = page_handler(request)
            else:
                response = page_handler.handle_get(request)

            # Fallback: ensure response is always a valid Response object
            if response is None:
                # Handler returned None, send server error response
                response = Response.server_error("Handler returned None")

            # Send response
            from RokCommon.web.request_response import send_response
            await send_response(writer, response)
            
            # Clean up request object
            if hasattr(request, 'clear_file_contents'):
                request.clear_file_contents()
            
            # Force garbage collection immediately after upload
            import gc
            gc.collect()
            
            # Longer delay for upload responses to prevent TCP reset
            if request.path == '/ota' and request.method == 'POST':
                await asyncio.sleep(0.5)  # Extended delay for OTA uploads to allow memory cleanup
            else:
                await asyncio.sleep(0.1)
        else:
            # 404 for unknown paths
            error_html = "<html><body><h1>404 Not Found</h1></body></html>"
            response_headers = f"HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\nContent-Length: {len(error_html)}\r\n\r\n"
            writer.write(response_headers.encode() + error_html.encode())
            await writer.drain()
            
            # Small delay before closing connection
            await asyncio.sleep(0.1)

        # Safer connection cleanup
        try:
            print("[WEB SERVER] Closing connection...")
            await writer.aclose()
            print("[WEB SERVER] Connection closed successfully")
            print("[WEB SERVER] Handler complete")
        except Exception as close_error:
            print(f"[WEB SERVER] Error closing connection: {close_error}")
            # Don't re-raise, connection cleanup errors are not critical

    except UnicodeError as unicode_error:
        # Known MicroPython bug: Empty UnicodeError during cleanup after processing binary files
        # This is harmless - the request was processed successfully before this error
        # Ignore harmless MicroPython UnicodeError during cleanup
        try:
            await writer.aclose()
        except Exception as close_error:
            pass
            pass
    except Exception as e:
        print(f"Web server error: {e}")
        try:
            await writer.aclose()
        except Exception as close_error:
            pass
            pass


async def _handle_api_request(writer, method, headers, path, query_string, body):
    """Handle API requests"""
    try:
        # Simple response for status
        if path == "/api/status":
            from RokCommon.variables.vars_store import get_config_value
            import gc
            
            # Get device information
            vehicle_name = get_config_value("vehicleName", "RokVision Device")
            device_type = get_config_value("vehicleType", "FPV Camera")
            project_type = get_config_value("projectType", "vision")
            
            # Get temperature if available
            mcu_temp = "N/A"
            try:
                import esp32
                temp_c = esp32.mcu_temperature()
                mcu_temp = round(temp_c, 1)
            except Exception:
                pass
            
            # Create status response
            status_data = {
                "status": "ok",
                "device": "RokVision", 
                "deviceName": vehicle_name,
                "deviceType": device_type,
                "projectType": project_type,
                "mcuTemp": mcu_temp,
                "memoryFree": gc.mem_free(),
                "uptime": 0
            }
            
            import ujson as json
            response = json.dumps(status_data)
            response_headers = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(response)}\r\n\r\n"
            writer.write(response_headers.encode() + response.encode())
        elif path == "/api/stop_stream":
            # Stream stop endpoint - try to cleanup gracefully 
            try:
                # For now, just return success since camera runs continuously
                # Future: could implement actual stream connection tracking
                response = '{"status": "ok", "message": "Stream stop acknowledged"}'
            except Exception as e:
                response = f'{{"status": "error", "message": "Stop failed: {e}"}}'
            response_headers = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(response)}\r\n\r\n"
            writer.write(response_headers.encode() + response.encode())
        else:
            # 404 for other API endpoints
            response = '{"error": "API endpoint not found"}'
            response_headers = f"HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\nContent-Length: {len(response)}\r\n\r\n"
            writer.write(response_headers.encode() + response.encode())
            
        await writer.drain()
        await writer.aclose()
        
    except Exception as e:
        print(f"API handler error: {e}")
        error_response = f'{{"error": "{str(e)}"}}'
        response_headers = f"HTTP/1.1 500 Internal Server Error\r\nContent-Type: application/json\r\nContent-Length: {len(error_response)}\r\n\r\n"
        try:
            writer.write(response_headers.encode() + error_response.encode())
            await writer.drain()
            await writer.aclose()
        except Exception:
            pass


async def _handle_static_assets(writer, path):
    """Handle static asset requests"""
    try:
        # Handle favicon redirect
        if path == "/favicon.ico":
            writer.write(
                b"HTTP/1.1 301 Moved Permanently\r\nLocation: /assets/favicon.ico\r\nCache-Control: max-age=86400\r\n\r\n"
            )
            await writer.drain()
            await writer.aclose()
            return

        # Try to serve static assets
        from RokCommon.web.static_assets import load_template
        
        sub = path[len("/assets/"):]
        
        # Try to load from RokVision assets first, then RokCommon
        content = None
        try_paths = [
            f"web/pages/assets/{sub}",
            f"RokCommon/web/pages/assets/{sub}"
        ]
        
        for try_path in try_paths:
            content = load_template(try_path)
            if content:
                break
        
        if content:
            # Determine content type
            if sub.endswith('.css'):
                content_type = 'text/css'
            elif sub.endswith('.js'):
                content_type = 'application/javascript'
            elif sub.endswith('.html'):
                content_type = 'text/html'
            elif sub.endswith('.ico'):
                content_type = 'image/x-icon'
            elif sub.endswith('.png'):
                content_type = 'image/png'
            elif sub.endswith('.jpg') or sub.endswith('.jpeg'):
                content_type = 'image/jpeg'
            else:
                content_type = 'text/plain'
                
            # Handle binary vs text content
            if sub.endswith(('.ico', '.png', '.jpg', '.jpeg', '.gif')):
                # For binary files, we need to read them as binary
                try:
                    # Re-read as binary since load_template returns text
                    for try_path in try_paths:
                        try:
                            with open(try_path, "rb") as f:
                                binary_content = f.read()
                            response_headers = f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\nContent-Length: {len(binary_content)}\r\nCache-Control: max-age=3600\r\n\r\n"
                            writer.write(response_headers.encode() + binary_content)
                            break
                        except:
                            continue
                    else:
                        # Fallback if binary read fails
                        writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
                except:
                    writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
            else:
                # Text content
                response_headers = f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\nContent-Length: {len(content)}\r\nCache-Control: max-age=3600\r\n\r\n"
                writer.write(response_headers.encode() + content.encode())
        else:
            # 404 for missing assets
            writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
            
        await writer.drain()
        await writer.aclose()
        
    except Exception as e:
        print(f"Static asset error: {e}")
        try:
            writer.write(b"HTTP/1.1 500 Internal Server Error\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
            await writer.aclose()
        except Exception:
            pass


async def _handle_legacy_status(writer):
    """Handle legacy /status endpoint"""
    try:
        # Redirect to API
        writer.write(b"HTTP/1.1 301 Moved Permanently\r\nLocation: /api/status\r\n\r\n")
        await writer.drain()
        await writer.aclose()
    except Exception:
        pass


async def start_web_server():
    """Start the web server and return the server object"""
    server = await asyncio.start_server(handle_client, "0.0.0.0", 80)
    print("Web server started on port 80")
    return server


def run():
    """Start the web server on port 80 (for backward compatibility)"""
    loop = asyncio.get_event_loop()
    loop.create_task(start_web_server())
    loop.run_forever()