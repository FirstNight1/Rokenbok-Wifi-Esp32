"""
Simple OTA placeholder handler
"""

def simple_ota_handler(request):
    """Simple OTA page with header nav and not implemented banner"""
    from RokCommon.web.pages.home_page import load_and_process_header
    from RokCommon.variables.vars_store import get_config_value
    
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
            elif isinstance(self.body, bytes):
                return self.body
            else:
                return str(self.body).encode('utf-8')
    
    try:
        # Load header nav
        header_nav = load_and_process_header(get_config_value("vehicleName", "Unknown"))
        
        # Create simple OTA page with header nav and not implemented banner
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OTA Updates</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background: #f0f0f0;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
        }}
        .banner {{
            background: #ff9800;
            color: white;
            padding: 15px;
            text-align: center;
            border-radius: 8px;
            margin: 20px 0;
            font-size: 18px;
            font-weight: bold;
        }}
        .content {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            border: 1px solid #ddd;
            text-align: center;
        }}
        h1 {{
            color: #333;
            margin-bottom: 20px;
        }}
        p {{
            color: #666;
            line-height: 1.6;
            margin: 10px 0;
        }}
    </style>
</head>
<body>
    {header_nav}
    <div class="container">
        <div class="banner">
            ⚠️ OTA UPDATE FUNCTIONALITY NOT CURRENTLY IMPLEMENTED ⚠️
        </div>
        <div class="content">
            <h1>Over-The-Air Updates</h1>
            <p>The OTA update functionality is planned for a future release.</p>
            <p>Currently, firmware updates must be performed manually using the flash tools.</p>
            <p>This page will be updated when OTA functionality is available.</p>
        </div>
    </div>
</body>
</html>"""
        return MinimalResponse('200 OK', 'text/html', html)
    except Exception as e:
        # Fallback in case of error
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>OTA Updates</title>
</head>
<body>
    <h1>OTA Updates</h1>
    <p>OTA functionality not currently implemented.</p>
    <p>Error loading page: {e}</p>
</body>
</html>"""
        return MinimalResponse('200 OK', 'text/html', html)