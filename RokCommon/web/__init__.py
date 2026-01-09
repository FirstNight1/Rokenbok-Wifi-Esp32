# Shared web components

from .request_response import Request, Response, PageHandler
from .web_handler import handle_request, UnifiedWebServer, create_routes_from_modules

__all__ = [
    "Request",
    "Response",
    "PageHandler",
    "handle_request",
    "UnifiedWebServer",
    "create_routes_from_modules",
]
