import uasyncio as asyncio
import sys
from web.pages import (
    admin_page,
    testing_page,
    play_page,
)
from RokCommon.ota import ota_page
from RokCommon.web import handle_request, create_routes_from_modules
from RokCommon.web.pages import wifi_page, home_page
from RokCommon.web.api_handler import create_api_handler
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


# Create routes using the unified home page
ROUTES = {
    "/": home_page.home_handler,
    "/wifi": wifi_page.wifi_handler,
    "/admin": admin_page,
    "/testing": testing_page,
    "/play": play_page,
    "/ota": ota_page.ota_handler,  # Use the new unified handler
}


# WebSocket handler for vehicle control
def vehicle_websocket_handler(text, writer):
    """Handle WebSocket messages for vehicle control"""
    try:
        import json
        import control.motor_controller as mc

        pkt = json.loads(text)
        if not isinstance(pkt, dict):
            return

        # Dispatch commands (set/stop/stop_all)
        action = pkt.get("action")
        if mc and action == "set":
            name = pkt.get("name")
            dir = pkt.get("dir", "fwd")
            power = float(pkt.get("power", 0))
            mc.motor_controller.set_motor(name, dir, power)
        elif mc and action == "stop":
            mc.motor_controller.stop_motor(pkt.get("name"))
        elif mc and action == "stop_all":
            mc.motor_controller.stop_all()
    except Exception as e:
        print(f"WebSocket handler error: {e}")


# Create simplified API handler
api_handler = create_api_handler()


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

    # Critical assets in order of size/importance (ota_page.html now unified in RokCommon)
    critical_assets = [
        "play_page.js",  # 17KB - largest, most interactive (optimized from 33KB)
        "testing_page.js",  # 10KB - testing functionality
        "play_page.html",  # 4KB - play page template
        "play_page.css",  # 3KB - play page styling
        "admin_page.html",  # 3KB - admin interface
        "mapping_modal.css",  # 2KB - control mapping styles
        "testing_page.html",  # 2KB - testing page
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

    for asset in critical_assets:
        fpath = "/".join([base_dir.rstrip("/"), "pages", "assets", asset])
        content = _load_template(fpath)
        if content:
            cached_count += 1
            total_size += len(content)
            print(f"  Cached: {asset} ({len(content)} bytes)")
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
    """Unified client handler with RokVehicle-specific features"""
    client_ip = "unknown"
    try:
        # Get client IP for logging
        try:
            client_ip = (
                writer.get_extra_info("peername")[0]
                if hasattr(writer, "get_extra_info")
                else "unknown"
            )
        except Exception:
            pass

        # Performance monitoring
        if perf_monitor:
            perf_monitor.log_request("unknown")

        # Memory pressure check
        if memory_pressure_check and memory_pressure_check():
            gc.collect()

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

        # Update performance monitoring with actual path
        if perf_monitor:
            perf_monitor.log_request(path)

        # Read headers
        headers = {}
        header_count = 0
        while header_count < 50:
            hdr = await reader.readline()
            if not hdr or hdr == b"\r\n":
                break
            try:
                line = hdr.decode().strip()
                header_count += 1
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip().lower()] = v.strip()
            except Exception:
                continue

        await asyncio.sleep(0)  # Yield control

        # Handle WebSocket upgrades (RokVehicle specific)
        if (
            headers.get("upgrade") == "websocket"
            and hashlib
            and "sec-websocket-key" in headers
        ):
            if path.startswith("/ws"):
                await _handle_websocket(reader, writer, headers, path)
                return

        # Handle static assets (RokVehicle specific)
        if path.startswith("/assets/") or path == "/favicon.ico":
            await _handle_static_assets(writer, path)
            return

        # Handle API endpoints via common API handler
        if path.startswith("/api/"):
            await _handle_api_request(
                reader, writer, method, headers, path, query_string
            )
            return

        # Handle legacy status endpoint (redirect to API)
        if path == "/status":
            await _handle_legacy_status(writer)
            return

        # Use unified handler for all page routes
        await handle_request(reader, writer, ROUTES, _load_template)

    except OSError as e:
        if getattr(e, "errno", None) == 104:  # ECONNRESET
            print(f"Client {client_ip} disconnected early")
        else:
            print(f"Network error handling request from {client_ip}: {e}")
    except Exception as e:
        print(f"Error handling request from {client_ip}: {e}")
        sys.print_exception(e)
    finally:
        try:
            await writer.aclose()
        except Exception:
            pass
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


async def _handle_api_request(reader, writer, method, headers, path, query_string):
    """Handle API requests via common API handler"""
    try:
        # Read body for POST requests
        body = ""
        if method == "POST":
            content_length = int(headers.get("content-length", 0))
            if content_length > 0:
                body_bytes = await reader.read(content_length)
                body = (
                    body_bytes.decode("utf-8")
                    if isinstance(body_bytes, bytes)
                    else str(body_bytes)
                )

        # Create Request object
        from RokCommon.web.request_response import Request

        request = Request(
            method=method,
            path=path,
            query_string=query_string,
            body=body,
            headers=headers,
            content_type=headers.get("content-type", ""),
        )

        # Handle via API handler
        response = await api_handler.handle(request)

        # Send response
        response_data = response.encode("utf-8")
        writer.write(response_data)
        await writer.drain()
        await writer.aclose()

    except Exception as e:
        print(f"API request error: {e}")
        try:
            writer.write(b"HTTP/1.1 500 Internal Server Error\r\n\r\n")
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
                break
            opcode, data = frame
            # opcode 8 = close
            if opcode == 8:
                break
            if opcode == 9:
                await _ws_send_text(writer, "")
                continue
            if opcode != 1:
                continue

            try:
                text = data.decode()
            except Exception as e:
                continue

            # parse JSON command
            import json

            try:
                pkt = json.loads(text)
            except Exception as e:
                pkt = None

            if not pkt or not isinstance(pkt, dict):
                continue

            # dispatch commands (set/stop/stop_all)
            action = pkt.get("action")
            if mc and action == "set":
                name = pkt.get("name")
                dir = pkt.get("dir", "fwd")
                power = float(pkt.get("power", 0))
                mc.motor_controller.set_motor(name, dir, power)
            elif mc and action == "stop":
                mc.motor_controller.stop_motor(pkt.get("name"))
            elif mc and action == "stop_all":
                mc.motor_controller.stop_all()

        except Exception as e:
            break

    try:
        await writer.aclose()
    except Exception:
        pass
    # unregister client
    WS_CLIENT = None


async def _keep_alive():
    # keeps asyncio loop alive
    while True:
        await asyncio.sleep(1)


def run():
    loop = asyncio.get_event_loop()
    loop.create_task(start_web_server())
    loop.create_task(_keep_alive())

    # Import UDP command queue
    try:
        from networking.udp_listener import cmd_queue
    except Exception:
        cmd_queue = None

    # If MotorController is present, schedule its async watchdog and UDP consumer
    try:
        import control.motor_controller as mc

        if hasattr(mc, "motor_controller") and hasattr(mc.motor_controller, "watchdog"):
            loop.create_task(mc.motor_controller.watchdog())

            # UDP command consumer: runs in main thread, processes queued UDP commands
            async def udp_consumer():
                loop_count = 0
                while True:
                    if cmd_queue:
                        cmds = cmd_queue.get_all()
                        for p in cmds:
                            if not isinstance(p, dict):
                                continue
                            action = p.get("action")
                            if action == "set":
                                name = p.get("name")
                                dir = p.get("dir", "fwd")
                                try:
                                    power = float(p.get("power", 0))
                                except Exception:
                                    power = 0
                                mc.motor_controller.set_motor(name, dir, power)
                            elif action == "stop":
                                mc.motor_controller.stop_motor(p.get("name"))
                            elif action == "stop_all":
                                mc.motor_controller.stop_all()

                    # Periodic GC to prevent memory buildup in UDP processing
                    loop_count += 1
                    if loop_count % 500 == 0:  # Every ~5 seconds at 10ms sleep
                        gc.collect()
                        loop_count = 0

                    await asyncio.sleep(0.01)

            loop.create_task(udp_consumer())
    except Exception:
        pass

    loop.run_forever()
