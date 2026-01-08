import uasyncio as asyncio
import sys
from web.pages import wifi_page, admin_page, home_page, testing_page, ota_page
from variables.vars_store import load_config
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

ROUTES = {
    "/": home_page,
    "/wifi": wifi_page,
    "/admin": admin_page,
    "/testing": testing_page,
    "/ota": ota_page,
}

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

    # Critical assets in order of size/importance for RokVision
    critical_assets = [
        "ota_page.html",  # 15KB - largest asset (optimized from 21KB)
        "admin_page.html",  # 8KB - admin interface
        "wifi_page.html",  # 4KB - wifi config
        "home_page.html",  # 3KB - home page
        "testing_page.html",  # 2KB - testing page
        "header_nav.html",  # 2KB - navigation
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
    client_ip = None
    try:
        # Get client IP for logging
        try:
            client_ip = (
                writer.get_extra_info("peername")[0]
                if hasattr(writer, "get_extra_info")
                else "unknown"
            )
        except Exception:
            client_ip = "unknown"

        # --- Read request line ---
        req_line = await reader.readline()
        if not req_line:
            await writer.aclose()
            return

        line = req_line.decode().strip()

        # Chrome HTTP/2 probe, reject immediately
        if line.startswith("PRI * HTTP/2.0"):
            await writer.aclose()
            return

        # Split safely (Chrome sometimes sends extra spaces)
        parts = line.split()
        if len(parts) < 2:
            await writer.aclose()
            return

        method = parts[0]
        full_path = parts[1]
        # Split path and query string
        if "?" in full_path:
            path, query_string = full_path.split("?", 1)
        else:
            path = full_path
            query_string = ""

        # Log request for performance monitoring
        if perf_monitor:
            perf_monitor.log_request(path)

        # Check memory pressure and force GC if needed
        if memory_pressure_check and memory_pressure_check():
            gc.collect()

        # --- Read headers until blank line ---
        headers = {}
        header_count = 0
        while header_count < 50:  # Limit headers to prevent DoS
            hdr = await reader.readline()
            if not hdr or hdr == b"\r\n":
                break
            try:
                line = hdr.decode().strip()
                header_count += 1
            except Exception:
                continue
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        # Yield control to prevent blocking
        await asyncio.sleep(0)

        # --- Favicon request (redirect to assets) ---
        if path == "/favicon.ico":
            # Redirect to the actual favicon location
            writer.write(
                b"HTTP/1.1 301 Moved Permanently\r\nLocation: /assets/favicon.ico\r\nCache-Control: max-age=86400\r\n\r\n"
            )
            await writer.drain()
            await writer.aclose()
            return

        # --- Static assets (serve files under /assets/) ---
        if path.startswith("/assets/"):
            import os

            # Map /assets/<name> -> web/pages/assets/<name>
            sub = path[len("/assets/") :]
            base_file = __file__
            # Compute base directory manually (MicroPython may not have os.path)
            if "/" in base_file:
                base_dir = base_file.rsplit("/", 1)[0]
            elif "\\" in base_file:
                base_dir = base_file.rsplit("\\", 1)[0]
            else:
                base_dir = "."

            fpath = "/".join([base_dir.rstrip("/"), "pages", "assets", sub.lstrip("/")])

            try:
                # Check if this is a binary asset type that should not be templated
                is_binary = (
                    fpath.endswith(".ico")
                    or fpath.endswith(".png")
                    or fpath.endswith(".jpg")
                    or fpath.endswith(".jpeg")
                    or fpath.endswith(".gif")
                    or fpath.endswith(".woff")
                    or fpath.endswith(".woff2")
                    or fpath.endswith(".ttf")
                )

                # Use template caching for text assets only
                if not is_binary:
                    content = _load_template(fpath)
                else:
                    content = None

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
                        content
                        if isinstance(content, bytes)
                        else content.encode("utf-8")
                    )
                    for i in range(0, len(content_bytes), 1024):
                        chunk = content_bytes[i : i + 1024]
                        writer.write(chunk)
                        await writer.drain()
                        # Yield control briefly between chunks
                        await asyncio.sleep_ms(1)

                    await writer.aclose()
                    return
                else:
                    # Fallback to file streaming for binary assets
                    try:
                        stat = os.stat(fpath)
                        clen = stat[6]
                        ctype = _get_content_type(fpath)

                        writer.write(
                            f"HTTP/1.1 200 OK\r\n"
                            f"Content-Type: {ctype}\r\n"
                            f"Content-Length: {clen}\r\n"
                            f"Cache-Control: no-store\r\n\r\n"
                        )
                        await writer.drain()

                        with open(fpath, "rb") as fh:
                            while True:
                                chunk = fh.read(
                                    512
                                )  # Smaller chunks for responsiveness
                                if not chunk:
                                    break
                                writer.write(chunk)
                                await writer.drain()
                                await asyncio.sleep_ms(1)  # Yield between chunks
                        await writer.aclose()
                        return
                    except Exception:
                        # File not found - fall through to route handling
                        pass
            except Exception:
                # File not found - fall through to route handling
                pass

        # --- /status endpoint ---
        if path == "/status":
            import json

            try:
                cfg = load_config()
            except Exception:
                cfg = {}

            # Read MCU temperature if available
            mcu_temp = None
            if esp32_available and hasattr(esp32, "mcu_temperature"):
                try:
                    mcu_temp = esp32.mcu_temperature()
                except Exception:
                    pass

            resp = {
                "type": cfg.get("vehicleType", "Unknown"),
                "tag": cfg.get("vehicleTag", "N/A"),
                "vehicleName": cfg.get("vehicleName", "Unnamed Vehicle"),
                "busy": False,  # RokVision doesn't use WebSocket control
                "battery": None,
                "mcu_temp": mcu_temp,
                "project": "RokVision",
            }

            json_response = json.dumps(resp)
            response = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{json_response}"
            writer.write(response.encode("utf-8"))
            await writer.drain()
            await writer.aclose()
            return

        # --- Route handling (GET/POST) ---
        page = ROUTES.get(path)
        if page:
            if method == "GET":
                try:
                    status, ctype, html = page.handle_get(query_string)
                except TypeError:
                    # Fallback for pages that don't accept query_string
                    status, ctype, html = page.handle_get()

                # Send response in chunks to prevent blocking
                header = f"HTTP/1.1 {status}\r\nContent-Type: {ctype}\r\n\r\n"
                writer.write(header)
                await writer.drain()

                # Chunked HTML delivery
                if isinstance(html, str):
                    html_bytes = html.encode("utf-8")
                else:
                    html_bytes = html

                for i in range(0, len(html_bytes), 1024):
                    chunk = html_bytes[i : i + 1024]
                    writer.write(chunk)
                    await writer.drain()
                    # Brief yield between chunks
                    await asyncio.sleep_ms(1)

                await writer.aclose()
                return

            elif method == "POST":
                # Read POST body
                content_length = int(headers.get("content-length", 0))
                body = await reader.read(content_length) if content_length else b""
                body = body.decode() if isinstance(body, bytes) else body

                # Load config for POST handler
                try:
                    cfg = load_config()
                except Exception:
                    cfg = None

                new_cfg, redirect = page.handle_post(body, cfg)

                writer.write(f"HTTP/1.1 303 See Other\r\nLocation: {redirect}\r\n\r\n")
                await writer.drain()
                await writer.aclose()
                return

    except Exception as e:
        print("Web server error:", e)
        sys.print_exception(e)


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
