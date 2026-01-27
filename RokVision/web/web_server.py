import uasyncio as asyncio
import sys
from web.pages.admin_page import admin_handler, snapshot_handler
from web.pages.testing_page import testing_handler
from RokCommon.web.pages import wifi_page, home_page
from RokCommon.variables.vars_store import get_config_value
import gc

# Import OTA handler directly
try:
    from RokCommon.ota.simple_ota import simple_ota_handler
except Exception as e:
    # Fallback handler if import fails
    def simple_ota_handler(request):
        class FallbackResponse:
            def __init__(self):
                self.status = '200 OK'
                self.content_type = 'text/html'
                self.body = '<html><body><h1>OTA Handler Import Failed</h1></body></html>'
                self.redirect = None
            def to_bytes(self):
                return self.body.encode('utf-8')
        return FallbackResponse()

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
    "/admin": admin_handler,
    "/testing": testing_handler,
    "/ota": simple_ota_handler,
    "/api/snapshot": snapshot_handler,
}


def _load_template(path):
    """Load template from file with caching"""
    if _cache_enabled and path in _template_cache:
        return _template_cache[path]
    
    try:
        with open(path, 'r') as f:
            content = f.read()
        
        if _cache_enabled:
            _template_cache[path] = content
        
        return content
    except Exception as e:
        print(f"Template load error for {path}: {e}")
        return None


def clear_template_cache():
    """Clear template cache to free memory or reload templates"""
    global _template_cache
    _template_cache.clear()
    gc.collect()


async def precache_critical_assets():
    """Pre-load critical static assets to improve page load performance"""
    global _cache_enabled

    if not _cache_enabled:
        return

    print("Pre-caching critical assets...")

    # Critical assets for RokVision (camera interface focused)
    critical_assets = [
        "admin_page.html",  # Admin interface with camera controls
        "testing_page.html",  # Testing page
    ]

    # RokCommon shared assets
    rokcommon_assets = [
        "home_page.html",  # Home page
        "wifi_page.html",  # WiFi configuration page
        "header_nav.html",  # Navigation header
        "ota_page.html",   # OTA update page
    ]

    # Get base directory for assets
    base_file = __file__
    if "/" in base_file:
        base_dir = base_file.rsplit("/", 1)[0]
    elif "\\" in base_file:
        base_dir = base_file.rsplit("\\", 1)[0]
    else:
        base_dir = "."

    cached_count = 0
    total_size = 0

    # Cache local assets
    for asset in critical_assets:
        fpath = "/".join([base_dir.rstrip("/"), "pages", "assets", asset])
        content = _load_template(fpath)
        if content:
            cached_count += 1
            total_size += len(content)
            print(f"  Cached: {asset} ({len(content)} bytes)")
        else:
            print(f"  Failed to cache: {asset}")

    # Cache RokCommon assets
    for asset in rokcommon_assets:
        fpath = f"RokCommon/web/pages/assets/{asset}"
        content = _load_template(fpath)
        if content:
            cached_count += 1
            total_size += len(content)
            print(f"  Cached: RokCommon/{asset} ({len(content)} bytes)")
        else:
            print(f"  Failed: {asset}")

        # Check memory pressure and yield control
        if memory_pressure_check and memory_pressure_check():
            print(
                f"  Memory pressure detected, stopping pre-cache after {cached_count} assets"
            )
            break

        await asyncio.sleep_ms(1)  # Yield to prevent blocking

    print(f"Pre-cache complete: {cached_count} assets, {total_size} bytes total")
    gc.collect()


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

        # Redirect status to API
        elif path == "/status":
            await write_http_redirect(writer, "/api/status")
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

            # Call the handler directly with proper error handling
            response = None
            try:
                if hasattr(page_handler, 'handle_get') and method == 'GET':
                    response = page_handler.handle_get(request)
                elif hasattr(page_handler, 'handle_post') and method == 'POST':
                    response = page_handler.handle_post(request)
                elif callable(page_handler):
                    # Handle simple function handlers (like OTA)
                    response = page_handler(request)
                else:
                    # Fallback - try calling as function
                    response = page_handler(request)
            except Exception as e:
                # Handler failed, create error response
                from RokCommon.web.request_response import Response
                response = Response.server_error(f"Handler error: {str(e)}")

            # Ensure response is always a valid Response object
            if response is None:
                from RokCommon.web.request_response import Response
                response = Response.server_error("Handler returned None")

            # Send response
            from RokCommon.web.request_response import send_response
            await send_response(writer, response)
            
            # Clean up request object
            if hasattr(request, 'clear_file_contents'):
                request.clear_file_contents()
            
            # Force garbage collection
            import gc
            gc.collect()
            
        else:
            # 404 for unknown paths
            error_html = "<html><body><h1>404 Not Found</h1></body></html>"
            response_headers = f"HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\nContent-Length: {len(error_html)}\r\n\r\n"
            writer.write(response_headers.encode() + error_html.encode())
            await writer.drain()

    except OSError as e:
        if getattr(e, "errno", None) != 104:  # Ignore ECONNRESET
            print(f"Network error: {e}")
    except Exception as e:
        print(f"Error handling request: {e}")
    finally:
        try:
            await writer.aclose()
        except Exception:
            pass
        gc.collect()


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
            # Stream stop endpoint - actually stop active streams
            try:
                from cam.camera_stream import stop_all_streams
                stopped_count = stop_all_streams()
                response = f'{{"status": "ok", "message": "Stopped {stopped_count} stream(s)", "count": {stopped_count}}}'
            except Exception as e:
                response = f'{{"status": "error", "message": "Stop failed: {e}"}}'
            response_headers = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(response)}\r\n\r\n"
            writer.write(response_headers.encode() + response.encode())
        elif path == "/api/snapshot":
            # Handle snapshot endpoint
            try:
                from RokCommon.web.request_response import Request
                request = Request(
                    method=method,
                    path=path,
                    query_string=query_string,
                    body=body,
                    headers=headers,
                    content_type=headers.get("content-type", ""),
                )
                
                from web.pages.admin_page import snapshot_handler
                response = await snapshot_handler(request)
                
                # Write response
                response_headers = f"HTTP/1.1 {response.status}\r\n"
                response_headers += f"Content-Type: {response.content_type}\r\n"
                response_headers += f"Content-Length: {len(response.body)}\r\n"
                response_headers += "\r\n"
                
                writer.write(response_headers.encode())
                if isinstance(response.body, bytes):
                    writer.write(response.body)
                else:
                    writer.write(response.body.encode())
                
            except Exception as e:
                print(f"Snapshot API error: {e}")
                response = f'{{"error": "Snapshot failed: {e}"}}'
                response_headers = f"HTTP/1.1 500 Internal Server Error\r\nContent-Type: application/json\r\nContent-Length: {len(response)}\r\n\r\n"
                writer.write(response_headers.encode() + response.encode())
        elif path == "/api/stream/restart":
            # Handle stream restart endpoint
            try:
                from cam.camera_stream import stop_all_streams, start_stream
                
                # Stop current streams
                stopped_count = stop_all_streams()
                
                # Brief pause for cleanup
                import uasyncio as asyncio
                await asyncio.sleep_ms(500)
                
                # Restart stream
                stream_started = await start_stream()
                
                if stream_started:
                    response = f'{{"status": "success", "message": "Stream restarted successfully", "stopped_count": {stopped_count}}}'
                else:
                    response = f'{{"status": "error", "message": "Failed to restart stream", "stopped_count": {stopped_count}}}'
                
                response_headers = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(response)}\r\n\r\n"
                writer.write(response_headers.encode() + response.encode())
                
            except Exception as e:
                print(f"Stream restart API error: {e}")
                response = f'{{"error": "Stream restart failed: {e}"}}'
                response_headers = f"HTTP/1.1 500 Internal Server Error\r\nContent-Type: application/json\r\nContent-Length: {len(response)}\r\n\r\n"
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
    # Pre-cache critical assets for faster page loads
    await precache_critical_assets()
    
    server = await asyncio.start_server(handle_client, "0.0.0.0", 80)
    print("Web server started on port 80")
    return server


def run():
    """Start the web server on port 80"""
    loop = asyncio.get_event_loop()
    loop.create_task(start_web_server())
    loop.run_forever()