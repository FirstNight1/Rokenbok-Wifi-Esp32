"""
Simple OTA placeholder handler
"""

def simple_ota_handler(request):
    # Use a minimal Response-like object compatible with send_response
    class MinimalResponse:
        def __init__(self, status, content_type, body):
            self.status = status
            self.content_type = content_type
            self.body = body
            self.redirect = None
        
        def to_bytes(self):
            if isinstance(self.body, str):
                return self.body.encode('utf-8')
            return self.body
    
    # Return a minimal HTML page
    html = "<html><body><h1>OTA Test</h1><p>Minimal handler works.</p></body></html>"
    return MinimalResponse('200 OK', 'text/html', html)