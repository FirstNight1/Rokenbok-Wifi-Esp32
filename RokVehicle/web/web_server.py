
import uasyncio as asyncio
from variables.vars_store import load_config
from web.pages import wifi_page, admin_page, home_page, testing_page
try:
    from control.power_manager import power_manager
except Exception:
    power_manager = None

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


# Only one controlling websocket client at a time
WS_CLIENTS = []
BUSY_CLIENT = None  # (writer, reader)
BUSY_FORCE_DISCONNECT = False

ROUTES = {
    "/": home_page,
    "/wifi": wifi_page,
    "/admin": admin_page,
    "/testing": testing_page,
}


async def handle_client(reader, writer):
    try:
        # If asleep, only allow wake via /admin POST
        if power_manager and power_manager.is_asleep():
            # Only allow POST to /admin to wake
            req_line = await reader.readline()
            if not req_line:
                await writer.aclose()
                return
            line = req_line.decode().strip()
            parts = line.split()
            if len(parts) < 2:
                await writer.aclose()
                return
            method = parts[0]
            full_path = parts[1]
            if method == 'POST' and full_path.startswith('/admin'):
                # allow admin POST to wake
                pass
            else:
                # respond with 503 Service Unavailable
                writer.write("HTTP/1.1 503 Service Unavailable\r\nContent-Type: text/plain\r\n\r\nVehicle is asleep. Use admin page to wake.")
                await writer.drain()
                await writer.aclose()
                return

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
        full_path = parts[1]
        # Split path and query string
        if '?' in full_path:
            path, query_string = full_path.split('?', 1)
        else:
            path = full_path
            query_string = ''
        # version = parts[2] if len(parts) >= 3 else "HTTP/1.0"

        # --- Read headers until blank line ---
        headers = {}
        cookies = {}
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
                if k.strip().lower() == 'cookie':
                    for c in v.strip().split(';'):
                        if '=' in c:
                            ck, cv = c.strip().split('=',1)
                            cookies[ck.strip()] = cv.strip()
        # --- Auth check for protected pages ---
        protected = path in ('/admin', '/wifi', '/testing')
        from variables.vars_store import load_config, check_password, encrypt_password, save_config
        session_ok = False
        session_token = cookies.get('session','')
        cfg = load_config()
        # Session token is just admin_user + enc_pass hashed (not secure, but simple)
        import hashlib
        def make_token(user, enc):
            return hashlib.sha1((user+enc).encode()).hexdigest()
        if session_token and session_token == make_token(cfg.get('admin_user','admin'), cfg.get('admin_pass','')):
            session_ok = True
        # Track failed logins
        failfile = '/variables/admin_fails.txt'
        fails = 0
        try:
            with open(failfile,'r') as f:
                fails = int(f.read().strip())
        except Exception:
            fails = 0
        # If protected and not logged in, show login form
        if protected and not session_ok:
            if method == 'POST':
                # Read up to 1024 bytes (safe for ESP32)
                body = await reader.read(1024)
                body = body.decode()
                # Parse POST fields
                fields = {}
                for pair in body.split('&'):
                    if '=' in pair:
                        k, v = pair.split('=', 1)
                        fields[k] = v.replace('+', ' ')
                user = fields.get('user','').strip()
                pw = fields.get('pw','').strip()
                # Sanitize
                import re
                user = re.sub(r'[^a-zA-Z0-9_\-]','',user)[:32]
                pw = pw[:64]
                if user == cfg.get('admin_user','admin') and check_password(pw, cfg.get('admin_pass','')):
                    # Success
                    session = make_token(user, cfg.get('admin_pass',''))
                    writer.write("HTTP/1.1 303 See Other\r\nSet-Cookie: session="+session+"; Path=/; HttpOnly\r\nLocation: "+path+"\r\n\r\n")
                    with open(failfile,'w') as f: f.write('0')
                    await writer.drain()
                    await writer.aclose()
                    return
                else:
                    fails += 1
                    with open(failfile,'w') as f: f.write(str(fails))
                    if fails >= 10:
                        # Reset admin, clear wifi, set DHCP
                        cfg['admin_user'] = 'admin'
                        cfg['admin_pass'] = encrypt_password('admin')
                        cfg['ssid'] = None
                        cfg['wifipass'] = None
                        cfg['ip_mode'] = 'dhcp'
                        save_config(cfg)
                        with open(failfile,'w') as f: f.write('0')
                        msg = "<p style='color:red'>Too many failed attempts. Admin and WiFi reset to defaults. Please login with admin/admin.</p>"
                    elif fails >= 5:
                        msg = "<p style='color:red'>Too many failed attempts. Connect via USB-C and run:<br><code>import variables.vars_store as v; c=v.load_config(); c['admin_user']='admin'; c['admin_pass']=v.encrypt_password('admin'); v.save_config(c)</code><br>Then reboot the board.</p>"
                    else:
                        msg = "<p style='color:red'>Login failed. Attempts: {}/10</p>".format(fails)
                    # Show login form again
                    writer.write("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n")
                    writer.write(f"""
<html><body><h2>Admin Login</h2>{msg}
<form method='POST'>
Username: <input name='user' maxlength='32'><br>
Password: <input name='pw' type='password' maxlength='64'><br>
<input type='submit' value='Login'>
</form></body></html>
""")
                    await writer.drain()
                    await writer.aclose()
                    return
            # GET: show login form
            writer.write("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n")
            writer.write("""
<html><body><h2>Admin Login</h2>
<form method='POST'>
Username: <input name='user' maxlength='32'><br>
Password: <input name='pw' type='password' maxlength='64'><br>
<input type='submit' value='Login'>
</form></body></html>
""")
            await writer.drain()
            await writer.aclose()
            return

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



        # --- /wifi_scan endpoint ---
        if path == '/wifi_scan':
            status, ctype, body = wifi_page.handle_wifi_scan()
            writer.write(f"HTTP/1.1 {status}\r\nContent-Type: {ctype}\r\n\r\n")
            writer.write(body)
            await writer.drain()
            await writer.aclose()
            return

        # --- /status endpoint ---
        if path == '/status':
            cfg = load_config()
            # busy if BUSY_CLIENT is not None
            busy = BUSY_CLIENT is not None
            # type, tag, vehicleName, battery (N/A)
            vtype = cfg.get('vehicleType')
            tag = cfg.get('vehicleTag')
            vname = cfg.get('vehicleName')
            # MCU temperature (Celsius)
            try:
                import esp32
                mcu_temp = esp32.mcu_temperature()
                if hasattr(mcu_temp, 'to_int'):
                    mcu_temp = float(mcu_temp)
            except Exception:
                mcu_temp = None
            resp = {
                'type': vtype,
                'tag': tag,
                'vehicleName': vname,
                'busy': busy,
                'battery': None,
                'mcu_temp': mcu_temp
            }
            import ujson as json
            writer.write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + json.dumps(resp))
            await writer.drain()
            await writer.aclose()
            return

        # --- /admin?force_disconnect=1 ---
        if path == '/admin' and 'force_disconnect=1' in query_string:
            global BUSY_FORCE_DISCONNECT
            BUSY_FORCE_DISCONNECT = True
            # respond immediately
            writer.write("HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nForce disconnect sent.")
            await writer.drain()
            await writer.aclose()
            return


        # ----------- GET -----------
        if method == "GET":
            # Pass query_string to handler if supported
            try:
                status, ctype, html = page.handle_get(query_string)
            except TypeError:
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

            # If waking, call power_manager.wake()
            if power_manager and 'wake' in body:
                power_manager.wake()

            writer.write(f"HTTP/1.1 303 See Other\r\nLocation: {redirect}\r\n\r\n")
            await writer.drain()
            await writer.aclose()
            return

        # Mark activity for auto-sleep
        if power_manager and not power_manager.is_asleep():
            power_manager.mark_active()
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

    global BUSY_CLIENT, BUSY_FORCE_DISCONNECT
    # Only allow one controlling client at a time
    if BUSY_CLIENT is not None:
        # Already busy
        await _ws_send_text(writer, '{"error":"Vehicle is busy"}')
        await writer.aclose()
        return
    BUSY_CLIENT = (writer, reader)
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
            # Check for force disconnect
            if BUSY_FORCE_DISCONNECT:
                BUSY_FORCE_DISCONNECT = False
                await _ws_send_text(writer, '{"error":"Force disconnect by admin"}')
                break
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
    global BUSY_CLIENT
    BUSY_CLIENT = None


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

    # Auto-sleep task
    if power_manager:
        async def auto_sleep_task():
            while True:
                if power_manager.should_sleep():
                    power_manager.shutdown()
                await asyncio.sleep(1)
        loop.create_task(auto_sleep_task())

    print("Web server background tasks scheduled.")
    loop.run_forever()
