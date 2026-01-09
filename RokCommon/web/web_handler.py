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
        method, path, query_string = parse_request_line(line)
        if not method or not path:
            await writer.aclose()
            return

        # Read headers
        header_lines = []
        header_count = 0
        while header_count < 50:  # Prevent header DoS
            hdr = await reader.readline()
            if not hdr or hdr == b"\r\n":
                break
            header_lines.append(hdr)
            header_count += 1

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

        # Route to page handler
        page_handler = routes.get(path)
        if page_handler:
            # Create legacy adapter if needed
            if not hasattr(page_handler, "handle"):
                page_handler = create_legacy_handler(page_handler)

            # Handle the request
            response = page_handler.handle(request)

            # Ensure we got a Response object
            if not isinstance(response, Response):
                print(
                    f"Warning: Handler for {path} returned non-Response object: {type(response)}"
                )
                response = Response.server_error("Invalid handler response")

            await send_response(writer, response)
        else:
            # 404 for unknown paths
            response = Response.not_found(f"Path {path} not found")
            await send_response(writer, response)

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
