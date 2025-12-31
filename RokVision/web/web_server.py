import uasyncio as asyncio
import sys
from web.pages import wifi_page, admin_page, home_page, testing_page
from variables.vars_store import load_config

try:
    import esp32

    esp32_available = True
except ImportError:
    esp32 = None
    esp32_available = False

ROUTES = {
    "/": home_page,
    "/wifi": wifi_page,
    "/admin": admin_page,
    "/testing": testing_page,
}

# Content type mapping for static assets
CONTENT_TYPES = {
    ".js": "application/javascript",
    ".css": "text/css",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".html": "text/html",
}


def _get_content_type(filepath):
    """Get content type based on file extension"""
    for ext, ctype in CONTENT_TYPES.items():
        if filepath.endswith(ext):
            return ctype
    return "application/octet-stream"


async def handle_client(reader, writer):
    try:

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
        # version = parts[2] if len(parts) >= 3 else "HTTP/1.0"

        # --- Read headers until blank line ---
        headers = {}
        while True:
            hdr = await reader.readline()
            if not hdr or hdr == b"\r\n":
                break
            try:
                line = hdr.decode().strip()
            except Exception:
                continue
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

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
                stat = os.stat(fpath)
                clen = stat[6]  # File size
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
                        chunk = fh.read(1024)
                        if not chunk:
                            break
                        writer.write(chunk)
                        await writer.drain()
                await writer.aclose()
                return
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

                writer.write(f"HTTP/1.1 {status}\r\nContent-Type: {ctype}\r\n\r\n")
                writer.write(html)
                await writer.drain()
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
