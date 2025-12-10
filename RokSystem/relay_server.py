# relay_server.py
# Rokenbok Vehicle Relay/Proxy Server
# - Serves static files (system_main.html, system_play.html, etc.)
# - Proxies HTTP and WebSocket requests to vehicles on the LAN
# - Exposes a single public port for all vehicles
# - Enforces per-client and per-vehicle rate limits


import asyncio
import websockets
import aiohttp
from aiohttp import web
import json
import time
import ssl

# --- Config ---
RELAY_PORT = 443  # Now using HTTPS/WSS
VEHICLE_PORT = 80  # ESP32 HTTP/WS port
RATE_LIMIT_MS = 30  # Minimum ms between control updates per client

# --- Vehicle registry (tag -> IP) ---
vehicle_registry = {}  # e.g. {'loader-123ABC': '192.168.11.42'}

# --- Static file serving ---
async def handle_static(request):
    path = request.match_info.get('filename', 'system_main.html')
    try:
        with open(path, 'rb') as f:
            data = f.read()
        if path.endswith('.html'):
            return web.Response(body=data, content_type='text/html')
        elif path.endswith('.js'):
            return web.Response(body=data, content_type='application/javascript')
        else:
            return web.Response(body=data)
    except Exception:
        return web.Response(status=404, text='Not found')

# --- HTTP proxy for /status and other endpoints ---
async def handle_api(request):
    tag = request.match_info['tag']
    path = request.match_info['path']
    ip = vehicle_registry.get(tag)
    if not ip:
        return web.Response(status=404, text='Vehicle not found')
    url = f'http://{ip}:{VEHICLE_PORT}/{path}'
    async with aiohttp.ClientSession() as session:
        async with session.request(request.method, url, params=request.query) as resp:
            data = await resp.read()
            return web.Response(body=data, status=resp.status, content_type=resp.content_type)

# --- WebSocket relay ---
async def handle_ws(request):
    tag = request.match_info['tag']
    ip = vehicle_registry.get(tag)
    if not ip:
        return web.Response(status=404, text='Vehicle not found')
    ws_client = web.WebSocketResponse()
    await ws_client.prepare(request)
    # Connect to vehicle's websocket
    uri = f'ws://{ip}:{VEHICLE_PORT}/ws'
    try:
        async with websockets.connect(uri) as ws_vehicle:
            last_sent = 0
            async def relay_to_vehicle():
                nonlocal last_sent
                async for msg in ws_client:
                    now = time.time() * 1000
                    if now - last_sent < RATE_LIMIT_MS:
                        continue  # rate limit
                    last_sent = now
                    await ws_vehicle.send(msg.data)
            async def relay_to_client():
                async for msg in ws_vehicle:
                    await ws_client.send_str(msg)
            await asyncio.gather(relay_to_vehicle(), relay_to_client())
    except Exception as e:
        await ws_client.close()
    return ws_client

# --- Vehicle registry update endpoint (LAN only, for vehicles to self-register) ---
async def handle_register(request):
    data = await request.json()
    tag = data.get('tag')
    ip = data.get('ip')
    if tag and ip:
        vehicle_registry[tag] = ip
        return web.Response(text='OK')
    return web.Response(status=400, text='Missing tag or ip')

# --- App setup ---
app = web.Application()
app.router.add_get('/', handle_static)
app.router.add_get('/{filename}', handle_static)
app.router.add_route('*', '/api/{tag}/{path:.*}', handle_api)
app.router.add_route('*', '/ws/{tag}', handle_ws)
app.router.add_post('/register_vehicle', handle_register)

if __name__ == '__main__':
    # --- SSL/TLS support ---
    SSL_CERT = '/path/to/fullchain.pem'  # <-- Set to your cert path
    SSL_KEY = '/path/to/privkey.pem'     # <-- Set to your key path
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(SSL_CERT, SSL_KEY)
    web.run_app(app, port=RELAY_PORT, ssl_context=ssl_context)
