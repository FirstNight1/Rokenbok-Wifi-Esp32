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

        # Initialize form dict - parsing will be done on-demand
        self.form = None
        self.files = {}  # Store uploaded files
        self._form_parsed = False
                    
    def _parse_form_data(self, body):
        """Parse URL-encoded form data with proper decoding"""
        for pair in body.split("&"):
            if "=" in pair:
                key, value = pair.split("=", 1)
                # Proper URL decoding
                key = self._url_decode(key).strip()
                value = self._url_decode(value).strip()
                self.form[key] = value
                
    def _url_decode(self, s):
        """Simple URL decoding for MicroPython"""
        # Handle + as space
        s = s.replace("+", " ")
        # Handle basic percent encoding
        i = 0
        result = ""
        while i < len(s):
            if s[i] == "%" and i + 2 < len(s):
                try:
                    hex_val = s[i+1:i+3]
                    char = chr(int(hex_val, 16))
                    result += char
                    i += 3
                except (ValueError, OverflowError):
                    result += s[i]
                    i += 1
            else:
                result += s[i]
                i += 1
        return result

    def get_query(self, key, default=None):
        """Get query parameter with default"""
        return self.query.get(key, default)

    def get_form(self, key, default=None):
        """Get form field with default"""
        if not self._form_parsed:
            self._ensure_form_parsed()
        return self.form.get(key, default)
    
    def get_files(self, field_name):
        """Get uploaded files for a given field name"""
        if not self._form_parsed:
            self._ensure_form_parsed()
        return self.files.get(field_name, [])
    
    def _ensure_form_parsed(self):
        """Parse form data on-demand"""
        if self._form_parsed:
            return
            
        self.form = {}
        
        if self.method == "POST" and self.body:
            # Check if Content-Type suggests form data
            ct = self.content_type.lower().split(";")[0].strip()
            is_form_content_type = ct == "application/x-www-form-urlencoded"
            is_multipart_content_type = ct == "multipart/form-data"
            
            # Only check for form-like body if it's a string (not binary)
            looks_like_form_data = (type(self.body) == str and 
                                   "=" in self.body and 
                                   ("&" in self.body or self.body.count("=") == 1))
            
            if is_multipart_content_type:
                self._parse_multipart_form_data()
            elif is_form_content_type or looks_like_form_data:
                try:
                    self._parse_form_data(self.body)
                except Exception:
                    pass
        
        self._form_parsed = True
    
    def _parse_multipart_form_data(self):
        """Parse multipart/form-data with binary support"""
        import gc
        try:
            # Extract boundary from content-type
            boundary = None
            if '; boundary=' in self.content_type:
                boundary = self.content_type.split('; boundary=')[1]
            
            if not boundary:
                return
                
            # Handle both binary and text body data
            if type(self.body) == bytes:
                boundary_marker = f'--{boundary}'.encode()
                parts = self.body.split(boundary_marker)
            else:
                boundary_marker = f'--{boundary}'
                parts = self.body.split(boundary_marker)
            
            files_parsed = 0
            fields_parsed = 0
            
            for part_idx, part in enumerate(parts):
                # Handle binary vs text parts
                if type(part) == bytes:
                    if not part or part == b'--\r\n' or part == b'--' or part == b'\r\n--\r\n':
                        continue
                    
                    # Skip initial CRLF
                    if part.startswith(b'\r\n'):
                        part = part[2:]
                    
                    # Find the double CRLF that separates headers from content
                    if b'\r\n\r\n' not in part:
                        continue
                    
                    headers_part, content = part.split(b'\r\n\r\n', 1)
                    headers_part = headers_part.decode('utf-8') if type(headers_part) == bytes else headers_part
                    headers_part = headers_part.decode('utf-8') if type(headers_part) == bytes else headers_part
                else:
                    if not part or part == '--\r\n' or part == '--':
                        continue
                    
                    # Skip initial CRLF
                    if part.startswith('\r\n'):
                        part = part[2:]
                    
                    # Find the double CRLF that separates headers from content
                    if '\r\n\r\n' not in part:
                        continue
                    
                    headers_part, content = part.split('\r\n\r\n', 1)
                
                # Parse Content-Disposition header to get field name
                if 'Content-Disposition: form-data' in headers_part:
                    field_name = None
                    filename = None
                    
                    # Extract name from: Content-Disposition: form-data; name="fieldname"
                    if 'name="' in headers_part:
                        start = headers_part.find('name="') + 6
                        end = headers_part.find('"', start)
                        if end > start:
                            field_name = headers_part[start:end]
                    
                    # Extract filename if present
                    if 'filename="' in headers_part:
                        start = headers_part.find('filename="') + 10
                        end = headers_part.find('"', start)
                        if end > start:
                            filename = headers_part[start:end]
                    
                    # Handle files vs form fields
                    if filename:
                        try:
                            # File upload - always treat as binary bytes
                            if type(content) == str:
                                content = content.encode('latin-1')  # Preserve all bytes
                            
                            # Instead of storing binary data, store only metadata to prevent Unicode errors
                            if field_name not in self.files:
                                self.files[field_name] = []
                            
                            # Store only filename and size, not the actual binary content
                            self.files[field_name].append({
                                'filename': filename,
                                'content': content,  # Keep for now but clear immediately after processing
                                'size': len(content),
                                'processed': True
                            })
                            files_parsed += 1
                            
                            # Force garbage collection after processing large files
                            if len(content) > 1024:  # Files larger than 1KB
                                gc.collect()
                        except Exception as e:
                            # Force GC on error and continue
                            gc.collect()
                    else:
                        # Form field - just string
                        if type(content) == bytes:
                            content = content.decode('utf-8', errors='ignore')
                        self.form[field_name] = content.rstrip('\r\n')
                        fields_parsed += 1
                        
        except Exception as e:
            # Force garbage collection on error
            import gc
            gc.collect()

    def clear_file_contents(self):
        """Clear binary file contents to prevent Unicode errors during garbage collection"""
        try:
            if hasattr(self, 'files') and self.files:
                for field_name, file_list in self.files.items():
                    for file_info in file_list:
                        if 'content' in file_info:
                            # Replace binary content with safe placeholder
                            file_info['content'] = b''
                print(f"[REQUEST] Cleared binary content from {len(self.files)} file fields")
        except Exception as e:
            print(f"[REQUEST] Error clearing file contents: {e}")

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
    def method_not_allowed(cls, message="Method not allowed"):
        """Create 405 response"""
        return cls.html(
            f"<html><body><h1>405 Method Not Allowed</h1><p>{message}</p></body></html>",
            status="405 Method Not Allowed",
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
        if type(self.body) == str:
            return self.body.encode("utf-8")
        elif type(self.body) == bytes:
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
                return Response.method_not_allowed(
                    f"Method {request.method} not supported"
                )
        except Exception as e:
            print(f"Error in page handler {self.__class__.__name__}: {e}")
            return Response.server_error(f"Handler error: {e}")

    def handle_get(self, request):
        """Override in subclasses for GET handling"""
        return Response.not_found("GET not implemented")

    def handle_post(self, request):
        """Override in subclasses for POST handling"""
        return Response.method_not_allowed(
            "POST not implemented"
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
                if type(line) == bytes
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
        
        # Ensure all data is sent before returning
        await writer.drain()

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

                            if type(result) == tuple:
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
