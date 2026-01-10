"""
Unified web server handler for RokCommon

This module provides a simplified web server request handler that works
with the unified Request/Response system, eliminating complex routing logic.

Key Features:
- Single async handler function that works with any web server
- Automatic Request object creation from raw HTTP data
- Response object handling with chunked transmission
- Legacy page handler support via adapters
- Memory-efficient processing for ESP32
"""

import uasyncio as asyncio
import time
from .request_response import (
    Request,
    Response,
    parse_request_line,
    parse_headers,
    send_response,
    create_legacy_handler,
)
import gc


async def handle_request(reader, writer, routes, template_loader=None):
    """
    Unified request handler that works with any web server setup

    Args:
        reader: AsyncIO reader for request data
        writer: AsyncIO writer for response data
        routes: Dict mapping paths to page handlers/modules
        template_loader: Optional function to load templates

    Returns:
        None (handles response directly)
    """
    client_ip = "unknown"
    print(f"[TRACE] handle_request called")
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

        print(f"[TRACE] Reading request line from {client_ip}")
        # WORKAROUND: Try to access underlying socket directly
        try:
            # Get the underlying socket from the asyncio stream
            sock = writer.get_extra_info("socket")
            if sock:
                print(f"[TRACE] Got underlying socket, trying direct recv")
                # Set socket to non-blocking mode and try direct recv
                try:
                    sock.setblocking(False)
                    raw_data = sock.recv(1024)
                    if raw_data:
                        print(f"[TRACE] Got {len(raw_data)} bytes via direct socket")
                    else:
                        print(f"[TRACE] No data from direct socket recv")
                        # Try with a small delay and retry
                        await asyncio.sleep(0.1)
                        raw_data = sock.recv(1024)
                        if raw_data:
                            print(f"[TRACE] Got {len(raw_data)} bytes on retry")
                        else:
                            print(f"[TRACE] Still no data, closing")
                            await writer.aclose()
                            return
                except OSError as e:
                    print(f"[TRACE] Direct socket recv failed: {e}")
                    # Fall back to asyncio with extended timeout
                    print(f"[TRACE] Falling back to asyncio read with 10s timeout")
                    try:
                        raw_data = await asyncio.wait_for(
                            reader.read(1024), timeout=10.0
                        )
                        if not raw_data:
                            print(f"[TRACE] No data from asyncio fallback, closing")
                            await writer.aclose()
                            return
                        print(
                            f"[TRACE] Got {len(raw_data)} bytes from asyncio fallback"
                        )
                    except asyncio.TimeoutError:
                        print(f"[TRACE] Asyncio fallback timeout, closing")
                        await writer.aclose()
                        return
            else:
                print(f"[TRACE] No underlying socket available")
                await writer.aclose()
                return
        except Exception as e:
            print(f"[TRACE] Socket access error: {e}, closing")
            await writer.aclose()
            return

        if not raw_data:
            print(f"[TRACE] No raw data received, closing")
            await writer.aclose()
            return

        print(f"[TRACE] Processing raw data: {len(raw_data)} bytes")

        # Find the first line (request line)
        try:
            data_str = raw_data.decode("utf-8", errors="ignore")
            lines = data_str.split("\n")
            if not lines or not lines[0].strip():
                print(f"[TRACE] No valid request line in raw data, closing")
                await writer.aclose()
                return

            line = lines[0].strip().rstrip("\r")
            print(f"[TRACE] Extracted request line: {line}")
        except Exception as e:
            print(f"[TRACE] Error processing raw data: {e}, closing")
            await writer.aclose()
            return

        # Handle HTTP/2 probes and malformed requests
        if line.startswith("PRI * HTTP/2.0") or not line:
            print(f"[TRACE] HTTP/2 or empty request, closing")
            await writer.aclose()
            return

        # Parse request line
        print(f"[TRACE] Parsing request line")
        method, path, query_string = parse_request_line(line)
        if not method or not path:
            print(f"[TRACE] Parse failed, closing")
            await writer.aclose()
            return

        print(f"[TRACE] Parsed: {method} {path}")

        # Read headers from the remaining raw data
        print(f"[TRACE] Parsing headers from raw data")
        header_lines = []
        if len(lines) > 1:
            # Skip the request line (lines[0]), process headers
            for i in range(1, len(lines)):
                line_data = lines[i].strip().rstrip("\r")
                if not line_data:  # Empty line = end of headers
                    break
                if line_data and ":" in line_data:
                    header_lines.append(line_data.encode("utf-8"))

        print(f"[TRACE] Got {len(header_lines)} headers from raw data")
        headers, content_type = parse_headers(header_lines)

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

        print(f"[TRACE] Creating Request object")
        # Create unified Request object
        request = Request(
            method=method,
            path=path,
            query_string=query_string,
            body=body,
            headers=headers,
            content_type=content_type,
        )

        # Yield control to prevent blocking
        await asyncio.sleep(0)

        print(f"[TRACE] Looking up route for {path}")
        # Route to page handler
        page_handler = routes.get(path)
        if page_handler:
            print(f"[TRACE] Found handler, creating adapter if needed")
            # Create legacy adapter if needed
            if not hasattr(page_handler, "handle"):
                page_handler = create_legacy_handler(page_handler)

            print(f"[TRACE] Calling handler")
            response = page_handler.handle(request)
            print(f"[TRACE] Handler returned: {type(response)}")

            # Ensure we got a Response object
            if not isinstance(response, Response):
                print(f"[TRACE] Invalid response type, creating error")
                response = Response.server_error("Invalid handler response")

            print(f"[TRACE] Sending response")
            await send_response(writer, response)
            print(f"[TRACE] Response sent successfully")
        else:
            print(f"[TRACE] No handler found, sending 404")
            # 404 for unknown paths
            response = Response.not_found(f"Path {path} not found")
            await send_response(writer, response)
            print(f"[TRACE] 404 sent successfully")

    except OSError as e:
        if getattr(e, "errno", None) == 104:  # ECONNRESET
            print(f"Client {client_ip} disconnected early")
        else:
            print(f"Network error handling request from {client_ip}: {e}")
    except Exception as e:
        print(f"Error handling request from {client_ip}: {e}")
        try:
            response = Response.server_error(str(e))
            await send_response(writer, response)
        except Exception:
            pass  # Can't do much if response sending fails
    finally:
        try:
            await writer.aclose()
        except Exception:
            pass

        # Help garbage collection
        gc.collect()


class UnifiedWebServer:
    """
    Optional wrapper class for creating web servers with unified handling

    This provides a clean interface for creating web servers that use
    the unified Request/Response system.
    """

    def __init__(self, routes, host="0.0.0.0", port=80, template_loader=None):
        self.routes = routes
        self.host = host
        self.port = port
        self.template_loader = template_loader
        self.server = None

    async def handle_client(self, reader, writer):
        """Client handler that uses unified request processing"""
        await handle_request(reader, writer, self.routes, self.template_loader)

    async def start(self):
        """Start the web server"""
        self.server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        print(f"Web server started on {self.host}:{self.port}")
        return self.server

    async def stop(self):
        """Stop the web server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            print("Web server stopped")


def create_routes_from_modules(**modules):
    """
    Helper function to create routes dict from page modules

    Example:
        routes = create_routes_from_modules(
            home=home_page,
            wifi=wifi_page,
            admin=admin_page
        )
    """
    routes = {}
    for path_name, module in modules.items():
        path = f"/{path_name}" if not path_name.startswith("/") else path_name
        routes[path] = module

    return routes
