"""
Unified Request/Response handling for RokCommon web framework

This module provides a standardized way to handle HTTP requests and responses
across all projects, eliminating the confusion of mixed return patterns.

Key Features:
- Single Request class with all HTTP data (method, path, query, body, headers)
- Single Response class with status, content-type, body, and redirect
- Consistent page handler interface: handler(request) -> response
- Automatic content-type detection and JSON serialization
- Memory-efficient string handling for ESP32
"""

try:
    import ujson as json
except ImportError:
    import json


class Request:
    """Unified HTTP request object"""

    def __init__(
        self,
        method="GET",
        path="/",
        query_string="",
        body="",
        headers=None,
        content_type="",
    ):
        self.method = method.upper()
        self.path = path
        self.query_string = query_string or ""
        self.body = body
        self.headers = headers or {}
        self.content_type = content_type

        # Parse query parameters
        self.query = {}
        if self.query_string:
            try:
                for pair in self.query_string.split("&"):
                    if "=" in pair:
                        key, value = pair.split("=", 1)
                        # URL decode basic cases
                        key = key.replace("+", " ").replace("%20", " ")
                        value = value.replace("+", " ").replace("%20", " ")
                        self.query[key] = value
            except Exception:
                pass  # Ignore malformed query strings

        # Parse form data if POST with form content
        self.form = {}
        if (
            self.method == "POST"
            and self.body
            and "application/x-www-form-urlencoded" in self.content_type
        ):
            try:
                for pair in self.body.split("&"):
                    if "=" in pair:
                        key, value = pair.split("=", 1)
                        # URL decode
                        key = key.replace("+", " ").replace("%20", " ")
                        value = value.replace("+", " ").replace("%20", " ")
                        self.form[key] = value
            except Exception:
                pass

    def get_query(self, key, default=None):
        """Get query parameter with default"""
        return self.query.get(key, default)

    def get_form(self, key, default=None):
        """Get form field with default"""
        return self.form.get(key, default)

    def is_multipart(self):
        """Check if request is multipart form data"""
        return "multipart/form-data" in self.content_type


class Response:
    """Unified HTTP response object"""

    def __init__(
        self, status="200 OK", content_type="text/html", body="", redirect=None
    ):
        self.status = status
        self.content_type = content_type
        self.body = body
        self.redirect = redirect

    @classmethod
    def html(cls, body, status="200 OK"):
        """Create HTML response"""
        return cls(status=status, content_type="text/html", body=body)

    @classmethod
    def json(cls, data, status="200 OK"):
        """Create JSON response"""
        try:
            body = json.dumps(data)
            return cls(status=status, content_type="application/json", body=body)
        except Exception as e:
            # Fallback error response
            return cls.json_error(f"JSON serialization failed: {e}")

    @classmethod
    def json_success(cls, message="Success", **kwargs):
        """Create successful JSON response"""
        data = {"success": True, "message": message}
        data.update(kwargs)
        return cls.json(data)

    @classmethod
    def json_error(cls, message="Error", status="400 Bad Request", **kwargs):
        """Create error JSON response"""
        data = {"success": False, "message": message}
        data.update(kwargs)
        return cls.json(data, status=status)

    @classmethod
    def redirect_to(cls, url):
        """Create redirect response"""
        return cls(status="303 See Other", redirect=url)

    @classmethod
    def not_found(cls, message="Page not found"):
        """Create 404 response"""
        return cls.html(
            f"<html><body><h1>404 Not Found</h1><p>{message}</p></body></html>",
            status="404 Not Found",
        )

    @classmethod
    def server_error(cls, message="Internal Server Error"):
        """Create 500 response"""
        return cls.html(
            f"<html><body><h1>500 Internal Server Error</h1><p>{message}</p></body></html>",
            status="500 Internal Server Error",
        )

    def to_bytes(self):
        """Convert response body to bytes for transmission"""
        if isinstance(self.body, str):
            return self.body.encode("utf-8")
        elif isinstance(self.body, bytes):
            return self.body
        else:
            return str(self.body).encode("utf-8")


class PageHandler:
    """Base class for page handlers with unified interface"""

    def handle(self, request):
        """Main entry point - routes to GET/POST handlers"""
        try:
            if request.method == "GET":
                return self.handle_get(request)
            elif request.method == "POST":
                return self.handle_post(request)
            else:
                return Response.json_error(
                    f"Method {request.method} not supported",
                    status="405 Method Not Allowed",
                )
        except Exception as e:
            print(f"Error in page handler {self.__class__.__name__}: {e}")
            return Response.server_error(f"Handler error: {e}")

    def handle_get(self, request):
        """Override in subclasses for GET handling"""
        return Response.not_found("GET not implemented")

    def handle_post(self, request):
        """Override in subclasses for POST handling"""
        return Response.json_error(
            "POST not implemented", status="405 Method Not Allowed"
        )


# Utility functions for web servers
def parse_request_line(line):
    """Parse HTTP request line safely"""
    try:
        parts = line.strip().split()
        if len(parts) < 2:
            return None, None, None

        method = parts[0]
        full_path = parts[1]

        # Split path and query string
        if "?" in full_path:
            path, query_string = full_path.split("?", 1)
        else:
            path, query_string = full_path, ""

        return method, path, query_string
    except Exception:
        return None, None, None


def parse_headers(lines):
    """Parse HTTP headers from lines"""
    headers = {}
    content_type = ""

    for line in lines:
        try:
            line_str = (
                line.decode("utf-8").strip()
                if isinstance(line, bytes)
                else line.strip()
            )
            if ":" in line_str:
                key, value = line_str.split(":", 1)
                header_key = key.strip().lower()
                header_value = value.strip()
                headers[header_key] = header_value

                if header_key == "content-type":
                    content_type = header_value
        except Exception:
            continue

    return headers, content_type


async def send_response(writer, response):
    """Send unified Response object to client"""
    try:
        # Handle redirects
        if response.redirect:
            header = (
                f"HTTP/1.1 {response.status}\r\nLocation: {response.redirect}\r\n\r\n"
            )
            writer.write(header)
            await writer.drain()
            return

        # Convert body to bytes
        body_bytes = response.to_bytes()

        # Send headers
        header = f"HTTP/1.1 {response.status}\r\nContent-Type: {response.content_type}\r\nContent-Length: {len(body_bytes)}\r\n\r\n"
        writer.write(header)
        await writer.drain()

        # Send body in chunks to prevent blocking
        chunk_size = 1024
        for i in range(0, len(body_bytes), chunk_size):
            chunk = body_bytes[i : i + chunk_size]
            writer.write(chunk)
            await writer.drain()

            # Yield control every 4KB to prevent blocking
            if i % (chunk_size * 4) == 0:
                import uasyncio as asyncio

                await asyncio.sleep(0)

    except Exception as e:
        print(f"Error sending response: {e}")
        # Try to send a basic error response
        try:
            error_msg = "HTTP/1.1 500 Internal Server Error\r\n\r\nResponse send failed"
            writer.write(error_msg)
            await writer.drain()
        except Exception:
            pass


# Legacy adapter functions for backward compatibility
def create_legacy_handler(page_module):
    """
    Create a wrapper that adapts old-style page handlers to new Request/Response system

    This allows gradual migration:
    - Old handlers: handle_get() -> (status, content_type, body)
    - Old handlers: handle_post(body, cfg) -> (cfg, redirect) or (cfg, redirect, json)
    - New handlers: handle(request) -> Response
    """

    class LegacyAdapter(PageHandler):
        def __init__(self, module):
            self.module = module

        def handle_get(self, request):
            try:
                # Try new style first
                if hasattr(self.module, "handle") and callable(self.module.handle):
                    return self.module.handle(request)

                # Try old style with query_string
                if hasattr(self.module, "handle_get"):
                    try:
                        status, content_type, body = self.module.handle_get(
                            request.query_string
                        )
                        return Response(
                            status=status, content_type=content_type, body=body
                        )
                    except TypeError:
                        # Fallback: old style without query_string
                        status, content_type, body = self.module.handle_get()
                        return Response(
                            status=status, content_type=content_type, body=body
                        )

                return Response.not_found()

            except Exception as e:
                print(f"Error in legacy GET handler: {e}")
                return Response.server_error(str(e))

        def handle_post(self, request):
            try:
                # Try new style first
                if hasattr(self.module, "handle") and callable(self.module.handle):
                    return self.module.handle(request)

                # Old style POST handling
                if hasattr(self.module, "handle_post"):
                    # Load config for legacy handlers
                    from RokCommon.variables.vars_store import get_config

                    cfg = get_config()

                    # Handle different old POST signatures
                    if hasattr(self.module, "handle_post"):
                        # Check if this is OTA-style (body, content_type, query_string)
                        if "ota" in str(self.module).lower():
                            result = self.module.handle_post(
                                request.body, request.content_type, request.query_string
                            )
                            if len(result) == 3:
                                status, content_type, body = result
                                return Response(
                                    status=status, content_type=content_type, body=body
                                )
                        else:
                            # Standard style (body, cfg)
                            result = self.module.handle_post(request.body, cfg)

                            if isinstance(result, tuple):
                                if len(result) == 3:
                                    # (cfg, redirect, json_response)
                                    new_cfg, redirect, json_response = result
                                    if json_response:
                                        return Response(
                                            status="200 OK",
                                            content_type="application/json",
                                            body=json_response,
                                        )
                                    elif redirect:
                                        return Response.redirect_to(redirect)
                                elif len(result) == 2:
                                    # (cfg, redirect)
                                    new_cfg, redirect = result
                                    if redirect:
                                        return Response.redirect_to(redirect)

                return Response.json_error("POST not implemented")

            except Exception as e:
                print(f"Error in legacy POST handler: {e}")
                return Response.json_error(
                    f"POST error: {e}", status="500 Internal Server Error"
                )

    return LegacyAdapter(page_module)
