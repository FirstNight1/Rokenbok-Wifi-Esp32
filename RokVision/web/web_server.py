import uasyncio as asyncio
import sys
from web.pages import admin_page, testing_page
from RokCommon.ota import ota_page
from RokCommon.web.pages import wifi_page, home_page
from RokCommon.web.api_handler import create_api_handler
from RokCommon.variables.vars_store import get_config_value
from RokCommon.web.request_response import Request, Response
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
    "/admin": admin_page.admin_handler,
    "/testing": testing_page.testing_handler,
    "/ota": ota_page.ota_handler,
}


def handle_stream_stop(request):
    """Handle camera stream stop requests"""
    try:
        from cam.camera_stream import stop_stream

        stop_stream()
        import json

        response_data = json.dumps(
            {"success": True, "message": "Camera stream stopped."}
        )
        return Response.json(response_data)
    except Exception as e:
        import json

        error_data = json.dumps(
            {"success": False, "message": f"Failed to stop stream: {e}"}
        )
        return Response(
            500,
            "Internal Server Error",
            error_data,
            {"Content-Type": "application/json"},
        )


# Custom API endpoints for RokVision
custom_endpoints = {"/stop_stream": handle_stream_stop}
api_handler = create_api_handler(custom_endpoints=custom_endpoints)

# Content type mapping for static assets
CONTENT_TYPES = {
    ".js": "application/javascript",
    ".css": "text/css",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
    ".gif": "image/gif",
    ".html": "text/html",
}


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


def _get_content_type(filepath):
    """Get content type based on file extension"""
    for ext, ctype in CONTENT_TYPES.items():
        if filepath.endswith(ext):
            return ctype
    return "application/octet-stream"


async def _handle_static_assets(writer, path):
    """Handle static asset requests"""
    import os

    # Map /assets/<name> -> web/pages/assets/<name>
    if path == "/favicon.ico":
        sub = "favicon.ico"
    else:
        sub = path[len("/assets/") :]

    base_file = __file__
    if "/" in base_file:
        base_dir = base_file.rsplit("/", 1)[0]
    elif "\\" in base_file:
        base_dir = base_file.rsplit("\\", 1)[0]
    else:
        base_dir = "."

    fpath = "/".join([base_dir.rstrip("/"), "pages", "assets", sub.lstrip("/")])

    try:
        content = _load_template(fpath)
        if content:
            ctype = _get_content_type(fpath)
            clen = (
                len(content)
                if isinstance(content, bytes)
                else len(content.encode("utf-8"))
            )

            writer.write(
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: {ctype}\r\n"
                f"Content-Length: {clen}\r\n"
                f"Cache-Control: no-store\r\n\r\n"
            )
            await writer.drain()

            # Send content in chunks
            content_bytes = (
                content if isinstance(content, bytes) else content.encode("utf-8")
            )
            for i in range(0, len(content_bytes), 1024):
                chunk = content_bytes[i : i + 1024]
                writer.write(chunk)
                await writer.drain()
                await asyncio.sleep_ms(1)
        else:
            # File not found
            writer.write(b"HTTP/1.1 404 Not Found\r\n\r\n404 Not Found")
            await writer.drain()
    except Exception:
        writer.write(b"HTTP/1.1 404 Not Found\r\n\r\n404 Not Found")
        await writer.drain()


async def _handle_api_request(writer, method, headers, path, query_string, body=""):
    """Handle API requests via common API handler"""
    try:
        # Create Request object with body already read
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

    except Exception as e:
        print(f"API request error: {e}")
        writer.write(b"HTTP/1.1 500 Internal Server Error\r\n\r\n")
        await writer.drain()


async def _handle_legacy_status(writer):
    """Handle legacy status endpoint"""
    import json

    try:
        from RokCommon.variables.vars_store import load_config

        cfg = load_config()
    except Exception:
        cfg = {}

    # Read MCU temperature if available
    mcu_temp = None
    temp_debug = "not_attempted"
    if esp32_available and hasattr(esp32, "mcu_temperature"):
        try:
            mcu_temp = esp32.mcu_temperature()
            temp_debug = f"success_{mcu_temp}"
        except Exception as e:
            temp_debug = f"mcu_temperature_error_{e}"
            # Try the alternate method
            try:
                if hasattr(esp32, "raw_temperature"):
                    mcu_temp = esp32.raw_temperature()
                    temp_debug = f"raw_success_{mcu_temp}"
            except Exception as e2:
                temp_debug = f"both_failed_{e}_{e2}"
    elif not esp32_available:
        temp_debug = "esp32_not_available"
    elif not hasattr(esp32, "mcu_temperature"):
        temp_debug = "mcu_temperature_not_found"

    resp = {
        "type": cfg.get("vehicleType", "Unknown"),
        "tag": cfg.get("vehicleTag", "N/A"),
        "vehicleName": cfg.get("vehicleName", "Unnamed Vehicle"),
        "busy": False,  # RokVision doesn't use WebSocket control
        "battery": None,
        "mcu_temp": mcu_temp,
        "temp_debug": temp_debug,  # Debug info
        "project": "RokVision",
    }

    json_response = json.dumps(resp)
    response = (
        f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{json_response}"
    )
    writer.write(response.encode("utf-8"))
    await writer.drain()


async def handle_client(reader, writer):
    """Clean client handler using only new Response architecture"""
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

        # --- Read request line ---
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

        # --- Read headers ---
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

        # --- Handle static assets ---
        if path.startswith("/assets/") or path == "/favicon.ico":
            await _handle_static_assets(writer, path)
            await writer.aclose()
            return

        # --- Handle API endpoints ---
        if path.startswith("/api/"):
            # Read POST body here in main handler to avoid double reading
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

            await _handle_api_request(writer, method, headers, path, query_string, body)
            await writer.aclose()
            return

        # --- Handle legacy status endpoint ---
        if path == "/status":
            await _handle_legacy_status(writer)
            await writer.aclose()
            return

        # --- Route handling using new Response architecture ---
        page = ROUTES.get(path)
        if page:
            try:
                # Create Request object
                request = Request(
                    method=method,
                    path=path,
                    query_string=query_string,
                    body="",
                    headers=headers,
                    content_type="",
                )

                if method == "GET":
                    # All handlers now return Response objects
                    response = page.handle_get(request)

                elif method == "POST":
                    # Read POST body
                    content_length = int(headers.get("content-length", 0))
                    if content_length > 0:
                        body_bytes = await reader.read(content_length)
                        body = (
                            body_bytes.decode("utf-8")
                            if isinstance(body_bytes, bytes)
                            else str(body_bytes)
                        )
                        request.body = body
                        request.content_type = headers.get("content-type", "")

                    # Handle POST and get redirect response
                    response = page.handle_post(request)

                    # Extract redirect from Response object
                    if (
                        "303" in response.status
                        or "302" in response.status
                        or "301" in response.status
                    ):
                        redirect = response.redirect or "/"
                    else:
                        redirect = "/"

                    writer.write(
                        f"HTTP/1.1 303 See Other\r\nLocation: {redirect}\r\n\r\n"
                    )
                    await writer.drain()
                    await writer.aclose()
                    return
                else:
                    # Method not allowed
                    response = Response(
                        405,
                        "Method Not Allowed",
                        "Method not allowed",
                        {"Content-Type": "text/plain"},
                    )

                # Ensure we got a valid Response object
                if not isinstance(response, Response):
                    response = Response.server_error("Invalid handler response")

                # Send the Response
                status_line = response.status
                content_type = response.content_type
                body_content = response.body

                # Send response in chunks to prevent blocking
                header = (
                    f"HTTP/1.1 {status_line}\r\nContent-Type: {content_type}\r\n\r\n"
                )
                writer.write(header)
                await writer.drain()

                # Chunked body delivery
                if isinstance(body_content, str):
                    body_bytes = body_content.encode("utf-8")
                else:
                    body_bytes = body_content

                for i in range(0, len(body_bytes), 1024):
                    chunk = body_bytes[i : i + 1024]
                    writer.write(chunk)
                    await writer.drain()
                    await asyncio.sleep_ms(1)

                await writer.aclose()
                return

            except Exception as e:
                print(f"Handler error for {path}: {e}")
                import sys

                sys.print_exception(e)
                # Send error response
                error_html = f"<html><body><h1>500 Internal Server Error</h1><p>{e}</p></body></html>"
                header = "HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/html\r\n\r\n"
                writer.write(header)
                writer.write(error_html.encode("utf-8"))
                await writer.drain()
                await writer.aclose()
                return
        else:
            # 404 for unknown paths
            writer.write(b"HTTP/1.1 404 Not Found\r\n\r\n404 Not Found")
            await writer.drain()
            await writer.aclose()
            return

    except Exception as e:
        print(f"Web server error from {client_ip}: {e}")
        sys.print_exception(e)
    finally:
        try:
            await writer.aclose()
        except Exception:
            pass
        gc.collect()


async def start_web_server():
    """Start the web server and keep it running"""
    server = await asyncio.start_server(handle_client, "0.0.0.0", 80)
    print("Web server started on port 80")

    # Keep the server running indefinitely - MicroPython style
    while True:
        await asyncio.sleep(1)


def run():
    """Start the web server on port 80 (for backward compatibility)"""
    loop = asyncio.get_event_loop()
    loop.create_task(start_web_server())
    loop.run_forever()
