import uasyncio as asyncio
import sys
from web.pages import admin_page, testing_page
from RokCommon.ota import ota_page
from RokCommon.web import handle_request, create_routes_from_modules
from RokCommon.web.pages import wifi_page, home_page
from RokCommon.web.api_handler import create_api_handler
from variables.vars_store import get_config_value
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


# Create routes using the unified home page
ROUTES = {
    "/": home_page.home_handler,
    "/wifi": wifi_page.wifi_handler,
    "/admin": admin_page,
    "/testing": testing_page,
    "/ota": ota_page.ota_handler,  # Use the new unified handler
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
        return (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(response_data)}\r\n"
            f"\r\n"
            f"{response_data}"
        )
    except Exception as e:
        import json

        error_data = json.dumps(
            {"success": False, "message": f"Failed to stop stream: {e}"}
        )
        return (
            f"HTTP/1.1 500 Internal Server Error\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(error_data)}\r\n"
            f"\r\n"
            f"{error_data}"
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

    # Critical assets in order of size/importance for RokVision (ota_page.html now unified in RokCommon)
    critical_assets = [
        "admin_page.html",  # 8KB - admin interface
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


def _get_content_type(filepath):
    """Get content type based on file extension"""
    for ext, ctype in CONTENT_TYPES.items():
        if filepath.endswith(ext):
            return ctype
    return "application/octet-stream"


async def handle_client(reader, writer):
    """Unified client handler with RokVision-specific features"""
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

        # Handle static assets (RokVision specific)
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

        # Handle legacy camera stream API (redirect to new API)
        if path == "/api/stop_stream" and method == "POST":
            await _handle_legacy_stream_stop(writer)
            return

        # Use unified handler for all page routes
        await handle_request(reader, writer, ROUTES, _load_template)

    except Exception as e:
        print(f"Error handling request from {client_ip}: {e}")
        sys.print_exception(e)
    finally:
        try:
            await writer.aclose()
        except Exception:
            pass
        gc.collect()


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


async def _handle_legacy_stream_stop(writer):
    """Handle legacy stream stop endpoint by redirecting to new API"""
    try:
        writer.write(
            b"HTTP/1.1 301 Moved Permanently\r\nLocation: /api/stop_stream\r\nCache-Control: no-cache\r\n\r\n"
        )
        await writer.drain()
        await writer.aclose()
    except Exception as e:
        print(f"Legacy stream stop redirect error: {e}")
        try:
            await writer.aclose()
        except Exception:
            pass


async def _handle_static_assets(writer, path):
    """Handle static asset requests for RokVision"""
    try:
        # Handle favicon redirect
        if path == "/favicon.ico":
            writer.write(
                b"HTTP/1.1 301 Moved Permanently\r\nLocation: /assets/favicon.ico\r\nCache-Control: max-age=86400\r\n\r\n"
            )
            await writer.drain()
            await writer.aclose()
            return

        import os

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
                ctype = _get_content_type(fpath)
                content_bytes = (
                    content.encode("utf-8") if isinstance(content, str) else content
                )

                writer.write(
                    f"HTTP/1.1 200 OK\r\nContent-Type: {ctype}\r\nContent-Length: {len(content_bytes)}\r\nCache-Control: no-store\r\n\r\n"
                )
                await writer.drain()

                # Send content in chunks
                for i in range(0, len(content_bytes), 1024):
                    chunk = content_bytes[i : i + 1024]
                    writer.write(chunk)
                    await writer.drain()
                    await asyncio.sleep_ms(1)

                await writer.aclose()
                return

        # Fallback to file streaming for binary assets or cache miss
        try:
            stat = os.stat(fpath)
            clen = stat[6]
            ctype = _get_content_type(fpath)

            writer.write(
                f"HTTP/1.1 200 OK\r\nContent-Type: {ctype}\r\nContent-Length: {clen}\r\nCache-Control: no-store\r\n\r\n"
            )
            await writer.drain()

            with open(fpath, "rb") as fh:
                while True:
                    chunk = fh.read(512)
                    if not chunk:
                        break
                    writer.write(chunk)
                    await writer.drain()
                    await asyncio.sleep_ms(1)
            await writer.aclose()
        except Exception:
            # File not found
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


async def start_web_server():
    """Start the web server and keep it running"""
    # Pre-cache critical assets for faster page loads
    await precache_critical_assets()

    server = await asyncio.start_server(handle_client, "0.0.0.0", 80)
    print("Web server started on port 80")

    # Keep the server running indefinitely - MicroPython style
    while True:
        await asyncio.sleep(1)


async def _keep_alive():
    """Keeps asyncio event loop alive"""
    while True:
        await asyncio.sleep(1)


def run():
    """Start the web server on port 80 (for backward compatibility)"""
    loop = asyncio.get_event_loop()
    loop.create_task(start_web_server())
    loop.run_forever()
