import uasyncio as asyncio
from variables.vars_store import load_config
from web.pages import wifi_page, admin_page, home_page, testing_page

import ubinascii
import os
try:
    import hashlib
except Exception:
    try:
        import uhashlib as hashlib
    except Exception:
        hashlib = None

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# list of websocket writer objects for broadcasting
WS_CLIENTS = []

ROUTES = {
    "/": home_page,
    "/wifi": wifi_page,
    "/admin": admin_page,
    "/testing": testing_page,
}


async def handle_client(reader, writer):
    try:
        # --- Read request line ---
        req_line = await reader.readline()
        if not req_line:
            await writer.aclose()
            return

        line = req_line.decode().strip()
        print("REQ:", line)

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
        path   = parts[1]
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

        # If this is a WebSocket upgrade, handle it here (path /ws)
        if headers.get('upgrade') == 'websocket' and hashlib and 'sec-websocket-key' in headers:
            # only allow upgrade on a dedicated path
            if path in ('/ws', '/testing_ws'):
                await _handle_websocket(reader, writer, headers, path)
                return

        # --- Static assets (serve files under /assets/) ---
        if path.startswith('/assets/'):
            # map /assets/<name> -> web/pages/assets/<name>
            sub = path[len('/assets/'):]
            # Some MicroPython ports don't include os.path; compute paths manually
            base_file = __file__
            if '/' in base_file:
                base_dir = base_file.rsplit('/', 1)[0]
            elif '\\' in base_file:
                base_dir = base_file.rsplit('\\', 1)[0]
            else:
                base_dir = '.'
            # join parts into a single posix-style path
            fpath = '/'.join([base_dir.rstrip('/'), 'pages', 'assets', sub.lstrip('/')])
            try:
                with open(fpath, 'rb') as fh:
                    data = fh.read()
                # simple content type detection
                if fpath.endswith('.js'):
                    ctype = 'application/javascript'
                elif fpath.endswith('.css'):
                    ctype = 'text/css'
                elif fpath.endswith('.png'):
                    ctype = 'image/png'
                elif fpath.endswith('.jpg') or fpath.endswith('.jpeg'):
                    ctype = 'image/jpeg'
                else:
                    ctype = 'application/octet-stream'

                # include content-length and cache-control
                clen = len(data)
                # For testing_page.js, disable caching for development
                if sub == 'testing_page.js':
                    cache_hdr = 'Cache-Control: no-store'
                else:
                    cache_hdr = 'Cache-Control: public, max-age=86400'
                writer.write(f"HTTP/1.1 200 OK\r\nContent-Type: {ctype}\r\nContent-Length: {clen}\r\n{cache_hdr}\r\n\r\n")
                # write raw bytes
                try:
                    writer.write(data)
                except Exception:
                    # fallback: write as decoded text
                    try:
                        writer.write(data.decode())
                    except Exception:
                        pass
                await writer.drain()
                await writer.aclose()
                return
            except Exception:
                # not found - fall through to route handling / redirect
                pass

        # --- Route selection ---
        page = ROUTES.get(path)
        if not page:
            writer.write("HTTP/1.1 302 Found\r\nLocation: /wifi\r\n\r\n")
            await writer.drain()
            await writer.aclose()
            return

        # ----------- GET -----------
        if method == "GET":
            status, ctype, html = page.handle_get()
            writer.write(f"HTTP/1.1 {status}\r\nContent-Type: {ctype}\r\n\r\n")
            writer.write(html)
            await writer.drain()
            await writer.aclose()
            return

        # ----------- POST -----------
        if method == "POST":
            # Read up to 1024 bytes (safe for ESP32)
            body = await reader.read(1024)
            body = body.decode()

            cfg = load_config()
            new_cfg, redirect = page.handle_post(body, cfg)

            writer.write(f"HTTP/1.1 303 See Other\r\nLocation: {redirect}\r\n\r\n")
            await writer.drain()
            await writer.aclose()
            return

    except Exception as e:
        print("Async Web Server Error:", e)


async def start_web_server():
    print("Starting async web server on port 80...")
    server = await asyncio.start_server(handle_client, "0.0.0.0", 80)
    print("Async web server running.")
    return server


async def _ws_recv_frame(reader):
    # minimal websocket frame reader (text frames only, assumes masked from client)
    hdr = await reader.read(2)
    if not hdr or len(hdr) < 2:
        return None
    b1 = hdr[0]
    b2 = hdr[1]
    fin = (b1 & 0x80) != 0
    opcode = b1 & 0x0f
    masked = (b2 & 0x80) != 0
    length = b2 & 0x7f
    if length == 126:
        ext = await reader.read(2)
        length = (ext[0] << 8) | ext[1]
    elif length == 127:
        # not expected on small devices
        ext = await reader.read(8)
        length = 0
        for i in range(8):
            length = (length << 8) | ext[i]

    mask_key = None
    if masked:
        mask_key = await reader.read(4)

    data = await reader.read(length) if length else b''
    if masked and mask_key:
        data = bytes([data[i] ^ mask_key[i % 4] for i in range(len(data))])

    return opcode, data


async def _ws_send_text(writer, text):
    # send a single text frame (no fragmentation)
    payload = text.encode()
    header = bytearray()
    header.append(0x81)  # FIN + text opcode
    L = len(payload)
    if L < 126:
        header.append(L)
    elif L < (1 << 16):
        header.append(126)
        header.extend(bytes([(L >> 8) & 0xff, L & 0xff]))
    else:
        header.append(127)
        header.extend(bytes([(L >> 56) & 0xff, (L >> 48) & 0xff, (L >> 40) & 0xff, (L >> 32) & 0xff,
                             (L >> 24) & 0xff, (L >> 16) & 0xff, (L >> 8) & 0xff, L & 0xff]))
    writer.write(header + payload)
    try:
        await writer.drain()
    except Exception:
        pass


async def _handle_websocket(reader, writer, headers, path):
    # perform handshake
    key = headers.get('sec-websocket-key')
    accept = None
    try:
        sha = hashlib.sha1()
        sha.update((key + WS_GUID).encode())
        accept = ubinascii.b2a_base64(sha.digest()).decode().strip()
    except Exception as e:
        print('WebSocket handshake failed:', e)
        try:
            await writer.aclose()
        except Exception:
            pass
        return

    resp = (
        'HTTP/1.1 101 Switching Protocols\r\n'
        'Upgrade: websocket\r\n'
        'Connection: Upgrade\r\n'
        f'Sec-WebSocket-Accept: {accept}\r\n\r\n'
    )
    writer.write(resp)
    await writer.drain()

    print('WebSocket connection established', path)
    # register this writer so server can broadcast stop events
    try:
        WS_CLIENTS.append(writer)
    except Exception:
        pass

    # websocket message loop
    try:
        import control.motor_controller as mc
    except Exception:
        mc = None

    while True:
        try:
            frame = await _ws_recv_frame(reader)
            if not frame:
                break
            opcode, data = frame
            # opcode 8 = close
            if opcode == 8:
                break
            if opcode == 9:
                # ping - reply pong
                await _ws_send_text(writer, '')
                continue
            if opcode != 1:
                continue

            try:
                text = data.decode()
            except Exception:
                continue

            # parse JSON command
            try:
                import ujson as json
            except Exception:
                import json

            try:
                pkt = json.loads(text)
            except Exception:
                pkt = None

            if not pkt or not isinstance(pkt, dict):
                continue

            # dispatch commands (set/stop/stop_all)
            action = pkt.get('action')
            if mc and action == 'set':
                name = pkt.get('name')
                dir = pkt.get('dir', 'fwd')
                power = float(pkt.get('power', 0))
                mc.motor_controller.set_motor(name, dir, power)
            elif mc and action == 'stop':
                mc.motor_controller.stop_motor(pkt.get('name'))
                # broadcast stop to other websocket clients so they can cancel local timers
                try:
                    try:
                        import ujson as _j
                    except Exception:
                        import json as _j
                    msg = _j.dumps({ 'action': 'stop', 'name': pkt.get('name') })
                    for w in list(WS_CLIENTS):
                        try:
                            await _ws_send_text(w, msg)
                        except Exception:
                            try:
                                WS_CLIENTS.remove(w)
                            except Exception:
                                pass
                except Exception:
                    pass
            elif mc and action == 'stop_all':
                mc.motor_controller.stop_all()
                # broadcast stop_all to other websocket clients so they can cancel local timers
                try:
                    try:
                        import ujson as _j
                    except Exception:
                        import json as _j
                    msg = _j.dumps({ 'action': 'stop_all' })
                    for w in list(WS_CLIENTS):
                        try:
                            await _ws_send_text(w, msg)
                        except Exception:
                            try:
                                WS_CLIENTS.remove(w)
                            except Exception:
                                pass
                except Exception:
                    pass

        except Exception as e:
            print('WebSocket loop error:', e)
            break

    try:
        await writer.aclose()
    except Exception:
        pass
    # unregister writer
    try:
        if writer in WS_CLIENTS:
            WS_CLIENTS.remove(writer)
    except Exception:
        pass


async def _keep_alive():
    # keeps asyncio loop alive
    while True:
        await asyncio.sleep(1)


def run():
    loop = asyncio.get_event_loop()
    loop.create_task(start_web_server())
    loop.create_task(_keep_alive())

    # Import UDP command queue
    try:
        from networking.udp_listener import cmd_queue
    except Exception:
        cmd_queue = None

    # If MotorController is present, schedule its async watchdog and UDP consumer
    try:
        import control.motor_controller as mc
        if hasattr(mc, 'motor_controller') and hasattr(mc.motor_controller, 'watchdog'):
            loop.create_task(mc.motor_controller.watchdog())

            # UDP command consumer: runs in main thread, processes queued UDP commands
            async def udp_consumer():
                while True:
                    if cmd_queue:
                        cmds = cmd_queue.get_all()
                        for p in cmds:
                            if not isinstance(p, dict):
                                continue
                            action = p.get('action')
                            if action == 'set':
                                name = p.get('name')
                                dir = p.get('dir', 'fwd')
                                try:
                                    power = float(p.get('power', 0))
                                except Exception:
                                    power = 0
                                mc.motor_controller.set_motor(name, dir, power)
                            elif action == 'stop':
                                mc.motor_controller.stop_motor(p.get('name'))
                            elif action == 'stop_all':
                                mc.motor_controller.stop_all()
                    await asyncio.sleep(0.01)
            loop.create_task(udp_consumer())
    except Exception:
        pass

    print("Web server background tasks scheduled.")
    loop.run_forever()
