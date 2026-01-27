import uasyncio as asyncio
import time
import sys
from web.pages.admin_page import admin_handler
from web.pages.testing_page import testing_handler
from web.pages.play_page import play_handler
from RokCommon.ota.simple_ota import simple_ota_handler
from RokCommon.web.pages import wifi_page, home_page
from RokCommon.variables.vars_store import get_config_value
import gc
import hashlib

# Import performance monitoring
try:
    from lib.performance_utils import perf_monitor, memory_pressure_check
except Exception:
    perf_monitor = None
    memory_pressure_check = None

try:
    import esp32
except ImportError:
    esp32 = None

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
WS_CLIENT = None  # Only one controlling websocket client

# Template cache to avoid file I/O on every request
_template_cache = {}
_cache_enabled = True


def get_effective_busy_status():
    """Get the effective busy status considering override settings"""
    from RokCommon.variables.vars_store import get_config_value
    
    override = get_config_value("busy_status_override", None)
    if override == "on":
        return True
    elif override == "off":
        return False
    else:  # override is None, "clear", or any other value
        # Use normal websocket connection status
        return bool(WS_CLIENT)


def set_busy_status_override(state):
    """Set busy status override state (on/off/clear)"""
    from RokCommon.variables.vars_store import save_config_value
    
    if state in ["on", "off"]:
        save_config_value("busy_status_override", state)
    else:
        # "clear" or any other value clears the override
        save_config_value("busy_status_override", None)
    
    return get_effective_busy_status()


# Create routes using the unified handlers
ROUTES = {
    "/": home_page.home_handler,
    "/wifi": wifi_page.wifi_handler,
    "/admin": admin_handler,
    "/testing": testing_handler,
    "/play": play_handler,
    "/ota": simple_ota_handler,
}


# WebSocket handler for vehicle control
def vehicle_websocket_handler(text, writer):
    """Handle WebSocket messages for vehicle control"""
    import time
    start_time = time.ticks_ms()
    
    try:
        import json
        import control.control_processor as cp

        json_parse_time = time.ticks_ms()
        pkt = json.loads(text)
        
        if not isinstance(pkt, dict):
            return

        # Use control processor for all packet handling
        if cp and cp.get_control_processor():
            cp.get_control_processor().process_packet(pkt)
        else:
            print("ERROR: Control processor not available")
            
    except Exception as e:
        end_time = time.ticks_ms()
        total_time = time.ticks_diff(end_time, start_time)
        print(f"WebSocket handler error: {e} (took {total_time}ms)")
        # Try to emergency stop all motors on any error
        try:
            import control.control_processor as cp
            if cp and cp.get_control_processor():
                cp.get_control_processor().stop_all_motors()
        except:
            pass


def _load_template(filepath):
    """Load and cache template files for better performance"""
    global _template_cache

    if not _cache_enabled or filepath not in _template_cache:
        try:
            with open(filepath, "r") as f:
                content = f.read()
            if _cache_enabled:
                _template_cache[filepath] = content
            return content
        except Exception as e:
            print(f"Template load error {filepath}: {e}")
            return None
    return _template_cache[filepath]


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

    # Critical assets in order of size/importance
    critical_assets = [
        "play_page.js",  # 17KB - largest, most interactive (optimized from 33KB)
        "testing_page.js",  # 10KB - testing functionality
        "play_page.html",  # 4KB - play page template
        "play_page.css",  # 3KB - play page styling
        "admin_page.html",  # 3KB - admin interface
        "mapping_modal.css",  # 2KB - control mapping styles
        "testing_page.html",  # 2KB - testing page
    ]

    # RokCommon shared assets
    rokcommon_assets = [
        "home_page.html",  # Home page
        "wifi_page.html",  # WiFi configuration page
        "header_nav.html",  # Navigation header
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
    """Client handler with WebSocket, API, and unified page handling"""
    client_ip = writer.get_extra_info('peername')[0] if writer.get_extra_info('peername') else 'unknown'
    start_time = time.time()
    
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

        # Handle WebSocket upgrades (RokVehicle specific)
        if (
            headers.get("upgrade") == "websocket"
            and "sec-websocket-key" in headers
        ):
            if path.startswith("/ws"):
                await _handle_websocket(reader, writer, headers, path)
                return

        # Handle static assets
        if path.startswith("/assets/") or path == "/favicon.ico":
            await _handle_static_assets(writer, path)
            return

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

        # Handle legacy status endpoint (redirect to API)
        if path == "/status":
            await _handle_legacy_status(writer)
            return

        # Handle page routes with unified handlers
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

            # Call the unified handler
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
        # Force garbage collection
        import gc
        gc.collect()


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

        # Extract asset path
        sub = path[len("/assets/") :]
        base_file = __file__
        if "/" in base_file:
            base_dir = base_file.rsplit("/", 1)[0]
        elif "\\" in base_file:
            base_dir = base_file.rsplit("\\", 1)[0]
        else:
            base_dir = "."

        fpath = "/".join([base_dir.rstrip("/"), "pages", "assets", sub.lstrip("/")])

        # Check if binary asset
        is_binary = any(
            fpath.endswith(ext)
            for ext in [
                ".ico",
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".woff",
                ".woff2",
                ".ttf",
            ]
        )

        # Try cached content for text assets
        if not is_binary:
            content = _load_template(fpath)
            if content:
                # Determine content type
                ctype = "text/plain"
                if fpath.endswith(".js"):
                    ctype = "application/javascript"
                elif fpath.endswith(".css"):
                    ctype = "text/css"
                elif fpath.endswith(".html"):
                    ctype = "text/html"

                content_bytes = content.encode("utf-8")
                writer.write(
                    f"HTTP/1.1 200 OK\r\nContent-Type: {ctype}\r\nContent-Length: {len(content_bytes)}\r\nCache-Control: max-age=300\r\n\r\n"
                )
                await writer.drain()
                writer.write(content_bytes)
                await writer.drain()
                await writer.aclose()
                return

        # Fallback to file streaming for binary assets or if cache missed
        import os

        try:
            stat = os.stat(fpath)
            clen = stat[6]

            ctype = "application/octet-stream"
            if fpath.endswith(".js"):
                ctype = "application/javascript"
            elif fpath.endswith(".css"):
                ctype = "text/css"
            elif fpath.endswith(".png"):
                ctype = "image/png"
            elif fpath.endswith((".jpg", ".jpeg")):
                ctype = "image/jpeg"
            elif fpath.endswith(".ico"):
                ctype = "image/x-icon"
            elif fpath.endswith(".gif"):
                ctype = "image/gif"

            writer.write(
                f"HTTP/1.1 200 OK\r\nContent-Type: {ctype}\r\nContent-Length: {clen}\r\nCache-Control: max-age=300\r\n\r\n"
            )
            await writer.drain()

            with open(fpath, "rb") as fh:
                while True:
                    chunk = fh.read(512)
                    if not chunk:
                        break
                    writer.write(chunk)
                    await writer.drain()
                    await asyncio.sleep(0)
            await writer.aclose()
        except Exception:
            # File not found - let it fall through to 404
            writer.write(b"HTTP/1.1 404 Not Found\r\n\r\n")
            await writer.drain()
            await writer.aclose()

    except Exception as e:
        print(f"Error serving static asset {path}: {e}")
        try:
            writer.write(b"HTTP/1.1 500 Internal Server Error\r\n\r\n")
            await writer.drain()
            await writer.aclose()
        except Exception:
            pass


async def _handle_api_request(writer, method, headers, path, query_string, body=""):
    """Handle API requests"""
    try:
        # Enhanced status response for RokVehicle
        if path == "/api/status":
            from RokCommon.variables.vars_store import get_config_value
            import gc
            
            # Get device information
            vehicle_name = get_config_value("vehicleName", "RokVehicle Device")
            vehicle_type = get_config_value("vehicleType", "vehicle")
            vehicle_tag = get_config_value("vehicleTag", "")
            project_type = get_config_value("projectType", "vehicle")
            
            # Get temperature if available
            mcu_temp = "N/A"
            try:
                if esp32:
                    temp_c = esp32.mcu_temperature()
                    mcu_temp = round(temp_c, 1)
            except Exception:
                pass
            
            # Get motor controller status if available
            motor_status = "N/A"
            active_motors = 0
            travel_limited = []
            try:
                import control.motor_controller as mc
                if hasattr(mc, "motor_controller"):
                    motor_status = "Available"
                    # Count active motors if possible
                    if hasattr(mc.motor_controller, "motors"):
                        active_motors = len([m for m in mc.motor_controller.motors.values() if getattr(m, "is_active", False)])
                    # Get travel limited motors from control processor
                    try:
                        from control.control_processor import get_control_processor
                        cp = get_control_processor()
                        if cp:
                            travel_limited = cp.get_travel_limited_motors()
                    except Exception:
                        travel_limited = []
            except Exception:
                pass
            
            # Get WiFi signal strength
            wifi_signal = 0
            try:
                import network
                sta = network.WLAN(network.STA_IF)
                if sta.active() and sta.isconnected():
                    wifi_signal = sta.status('rssi')
                else:
                    wifi_signal = 0  # AP mode or disconnected
            except Exception:
                wifi_signal = 0
            
            # Create enhanced status response
            status_data = {
                "status": "ok",
                "device": "RokVehicle", 
                "deviceName": vehicle_name,
                "deviceType": vehicle_type,
                "deviceTag": vehicle_tag,
                "projectType": project_type,
                "mcuTemp": mcu_temp,
                "memoryFree": gc.mem_free(),
                "motorController": motor_status,
                "activeMotors": active_motors,
                "busy": get_effective_busy_status(),
                "busyStatusOverride": get_config_value("busy_status_override", None),
                "travelLimitedMotors": travel_limited,
                "wifiSignal": wifi_signal,
                "uptime": 0
            }
            
            import ujson as json
            response = json.dumps(status_data)
            response_headers = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(response)}\r\n\r\n"
            writer.write(response_headers.encode() + response.encode())
        
        elif path == "/api/busy-override" and method == "POST":
            # Handle busy status override
            try:
                import ujson as json
                data = json.loads(body) if body else {}
                state = data.get("state", "clear")
                
                effective_busy = set_busy_status_override(state)
                
                response_data = {
                    "success": True,
                    "busyStatusOverride": get_config_value("busy_status_override", None),
                    "effectiveBusyStatus": effective_busy,
                    "message": f"Busy status override set to '{state}'"
                }
                
                response = json.dumps(response_data)
                response_headers = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(response)}\r\n\r\n"
                writer.write(response_headers.encode() + response.encode())
                
            except Exception as e:
                error_response = f'{{"error": "Failed to set busy override: {str(e)}"}}'  
                response_headers = f"HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\nContent-Length: {len(error_response)}\r\n\r\n"
                writer.write(response_headers.encode() + error_response.encode())
        
        else:
            # 404 for other API endpoints
            response = '{"error": "API endpoint not found"}'
            response_headers = f"HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\nContent-Length: {len(response)}\r\n\r\n"
            writer.write(response_headers.encode() + response.encode())
            
        await writer.drain()
        await writer.aclose()

    except Exception as e:
        print(f"API request error: {e}")
        error_response = f'{{"error": "{str(e)}"}}'
        response_headers = f"HTTP/1.1 500 Internal Server Error\r\nContent-Type: application/json\r\nContent-Length: {len(error_response)}\r\n\r\n"
        try:
            writer.write(response_headers.encode() + error_response.encode())
            await writer.drain()
            await writer.aclose()
        except Exception:
            pass


async def _handle_legacy_status(writer):
    """Handle legacy /status endpoint by redirecting to /api/status"""
    try:
        writer.write(
            b"HTTP/1.1 301 Moved Permanently\r\nLocation: /api/status\r\nCache-Control: no-cache\r\n\r\n"
        )
        await writer.drain()
        await writer.aclose()
    except Exception as e:
        print(f"Legacy status redirect error: {e}")
        try:
            await writer.aclose()
        except Exception:
            pass


async def start_web_server():
    # Pre-cache critical assets for faster page loads
    await precache_critical_assets()

    server = await asyncio.start_server(handle_client, "0.0.0.0", 80)
    return server


async def _ws_recv_frame(reader):
    # minimal websocket frame reader (text frames only, assumes masked from client)
    hdr = await reader.read(2)
    if not hdr or len(hdr) < 2:
        return None
    b1 = hdr[0]
    b2 = hdr[1]
    fin = (b1 & 0x80) != 0
    opcode = b1 & 0x0F
    masked = (b2 & 0x80) != 0
    length = b2 & 0x7F
    if length == 126:
        ext = await reader.read(2)
        length = (ext[0] << 8) | ext[1]
    elif length == 127:
        # not expected on small devices
        ext = await reader.read(8)
        length = 0
        for i in range(8):
            length = (length << 8) | ext[i]

    mask_key = None
    if masked:
        mask_key = await reader.read(4)

    data = await reader.read(length) if length else b""
    if masked and mask_key:
        data = bytes([data[i] ^ mask_key[i % 4] for i in range(len(data))])

    return opcode, data


async def _ws_send_text(writer, text):
    # send a single text frame (no fragmentation)
    payload = text.encode()
    header = bytearray()
    header.append(0x81)  # FIN + text opcode
    L = len(payload)
    if L < 126:
        header.append(L)
    elif L < (1 << 16):
        header.append(126)
        header.extend(bytes([(L >> 8) & 0xFF, L & 0xFF]))
    else:
        header.append(127)
        header.extend(
            bytes(
                [
                    (L >> 56) & 0xFF,
                    (L >> 48) & 0xFF,
                    (L >> 40) & 0xFF,
                    (L >> 32) & 0xFF,
                    (L >> 24) & 0xFF,
                    (L >> 16) & 0xFF,
                    (L >> 8) & 0xFF,
                    L & 0xFF,
                ]
            )
        )
    writer.write(header + payload)
    try:
        await writer.drain()
    except Exception:
        pass


async def _handle_websocket(reader, writer, headers, path):
    # perform handshake
    key = headers.get("sec-websocket-key")
    accept = None
    try:
        sha = hashlib.sha1()
        sha.update((key + WS_GUID).encode())
        import ubinascii

        accept = ubinascii.b2a_base64(sha.digest()).decode().strip()
    except Exception as e:
        try:
            await writer.aclose()
        except Exception:
            pass
        return

    resp = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
    )
    writer.write(resp)
    await writer.drain()

    # Only allow one controlling client at a time
    global WS_CLIENT
    if WS_CLIENT:
        await _ws_send_text(writer, '{"error":"Vehicle is busy"}')
        await writer.aclose()
        return
    WS_CLIENT = (writer, reader)

    # websocket message loop

    try:
        import control.motor_controller as mc
    except Exception as e:
        mc = None

    while True:
        try:
            frame = await _ws_recv_frame(reader)
            if not frame:
                print("WebSocket: No frame received, closing connection")
                break
            opcode, data = frame
            # opcode 8 = close
            if opcode == 8:
                print("WebSocket: Close frame received")
                break
            if opcode == 9:
                await _ws_send_text(writer, "")
                continue
            if opcode != 1:
                continue

            try:
                text = data.decode()
            except Exception as e:
                print(f"WebSocket: Error decoding message: {e}")
                continue

            # parse JSON command
            import json

            try:
                pkt = json.loads(text)
            except Exception as e:
                print(f"WebSocket: JSON parse error: {e}")
                pkt = None

            if not pkt or not isinstance(pkt, dict):
                continue

            # Check if this is a control packet (has axisMotors, functionMotors, etc.) or action packet
            action = pkt.get("action")
            if action:
                # Handle legacy action-based packets (set/stop/stop_all)
                if mc and action == "set":
                    name = pkt.get("name")
                    dir = pkt.get("dir", "fwd")
                    power = float(pkt.get("power", 0))
                    mc.motor_controller.set_motor(name, dir, power)
                elif mc and action == "stop":
                    mc.motor_controller.stop_motor(pkt.get("name"))
                elif mc and action == "stop_all":
                    mc.motor_controller.stop_all()
            else:
                # Handle modern control packets via control processor
                vehicle_websocket_handler(text, writer)

        except Exception as e:
            print(f"WebSocket: Error in message loop: {e}")
            break

    print("WebSocket: Connection closing, cleaning up...")
    try:
        await writer.aclose()
    except Exception as e:
        print(f"WebSocket: Error closing writer: {e}")
    # unregister client
    if WS_CLIENT and WS_CLIENT[0] == writer:
        WS_CLIENT = None
        print("WebSocket: Client unregistered")


async def _keep_alive():
    # keeps asyncio loop alive
    while True:
        await asyncio.sleep(1)


def run():
    # Use existing event loop for MicroPython compatibility
    loop = asyncio.get_event_loop()

    loop.create_task(start_web_server())
    loop.create_task(_keep_alive())

    # Initialize control processor with motor and function controllers
    try:
        import control.motor_controller as mc
        import control.control_processor as cp

        if hasattr(mc, "motor_controller"):
            # Get function controller from motor controller if available
            function_controller = None
            if hasattr(mc.motor_controller, "function_controller"):
                function_controller = mc.motor_controller.function_controller
            
            # Create and set global control processor
            control_processor = cp.ControlProcessor(mc.motor_controller, function_controller)
            cp.set_control_processor(control_processor)
            print("Control processor initialized")
        else:
            print("Motor controller not available for control processor")
    except Exception as e:
        print(f"Control processor initialization error: {e}")

    # Motor controller no longer has a watchdog - control_processor handles safety
    # Control processor watchdog is started automatically when initialized
    
    loop.run_forever()
