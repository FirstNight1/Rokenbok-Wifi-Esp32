"""
Shared Static Asset Utilities for RokCommon

This module provides common utilities for serving static assets across projects:
- Content type mapping
- Template caching system
- Asset serving utilities
- Unified HTTP responses
"""

import gc


# Universal content type mapping
CONTENT_TYPES = {
    ".js": "application/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".eot": "application/vnd.ms-fontobject",
    ".json": "application/json",
    ".txt": "text/plain",
    ".md": "text/markdown",
}

# Global template cache for performance
_template_cache = {}
_cache_enabled = True


def get_content_type(filepath):
    """Get content type based on file extension"""
    for ext, ctype in CONTENT_TYPES.items():
        if filepath.endswith(ext):
            return ctype
    return "application/octet-stream"


def is_binary_asset(filepath):
    """Check if file is a binary asset that shouldn't be cached in memory"""
    binary_extensions = [
        ".ico",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
    ]
    return any(filepath.endswith(ext) for ext in binary_extensions)


def load_template(filepath):
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


def enable_template_cache(enabled=True):
    """Enable or disable template caching globally"""
    global _cache_enabled
    _cache_enabled = enabled


async def serve_static_asset(writer, filepath, cache_control="max-age=300"):
    """
    Unified static asset serving with caching support

    Args:
        writer: AsyncIO writer for response
        filepath: Full path to asset file
        cache_control: Cache control header value
    """
    try:
        is_binary = is_binary_asset(filepath)

        # Try cached content for text assets
        if not is_binary:
            content = load_template(filepath)
            if content:
                content_type = get_content_type(filepath)
                content_bytes = content.encode("utf-8")

                writer.write(
                    f"HTTP/1.1 200 OK\r\n"
                    f"Content-Type: {content_type}\r\n"
                    f"Content-Length: {len(content_bytes)}\r\n"
                    f"Cache-Control: {cache_control}\r\n\r\n"
                )
                await writer.drain()
                writer.write(content_bytes)
                await writer.drain()
                await writer.aclose()
                return True

        # Fallback to file streaming for binary assets or cache miss
        import os

        try:
            stat = os.stat(filepath)
            file_size = stat[6]
            content_type = get_content_type(filepath)

            writer.write(
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: {content_type}\r\n"
                f"Content-Length: {file_size}\r\n"
                f"Cache-Control: {cache_control}\r\n\r\n"
            )
            await writer.drain()

            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(512)
                    if not chunk:
                        break
                    writer.write(chunk)
                    await writer.drain()
                    import uasyncio as asyncio

                    await asyncio.sleep_ms(1)  # Yield to prevent blocking

            await writer.aclose()
            return True

        except Exception:
            # File not found or read error
            return False

    except Exception as e:
        print(f"Error serving static asset {filepath}: {e}")
        return False


async def send_404(writer):
    """Send a 404 Not Found response"""
    try:
        writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
        await writer.drain()
        await writer.aclose()
    except Exception:
        pass


async def send_500(writer, error_msg="Internal Server Error"):
    """Send a 500 Internal Server Error response"""
    try:
        error_content = f"Error: {error_msg}"
        error_bytes = error_content.encode("utf-8")
        writer.write(
            f"HTTP/1.1 500 Internal Server Error\r\n"
            f"Content-Type: text/plain\r\n"
            f"Content-Length: {len(error_bytes)}\r\n\r\n"
        )
        await writer.drain()
        writer.write(error_bytes)
        await writer.drain()
        await writer.aclose()
    except Exception:
        pass


async def send_redirect(writer, location, permanent=False):
    """Send a redirect response"""
    try:
        status = "301 Moved Permanently" if permanent else "302 Found"
        writer.write(
            f"HTTP/1.1 {status}\r\n"
            f"Location: {location}\r\n"
            f"Content-Length: 0\r\n\r\n".encode()
        )
        await writer.drain()
        await writer.aclose()
    except Exception:
        pass


def resolve_asset_path(base_file, asset_name):
    """
    Resolve full path to an asset file based on the calling module's location

    Args:
        base_file: __file__ from the calling module
        asset_name: Name of asset file (e.g., "favicon.ico")

    Returns:
        Full path to asset file
    """
    if "/" in base_file:
        base_dir = base_file.rsplit("/", 1)[0]
    elif "\\" in base_file:
        base_dir = base_file.rsplit("\\", 1)[0]
    else:
        base_dir = "."

    return "/".join([base_dir.rstrip("/"), "pages", "assets", asset_name.lstrip("/")])
