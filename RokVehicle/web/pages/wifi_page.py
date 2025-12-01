from variables.vars_store import load_config, save_config
import sys
import ubinascii
import os
try:
    import ucryptolib as cryptolib
except Exception:
    cryptolib = None
try:
    import network
except Exception:
    network = None


# ---------------------------------------------------------
# HTML Builders
# ---------------------------------------------------------

def build_wifi_page(cfg, scan_results=None, status_info=None):
    ssid_val = cfg.get("ssid") or ""
    vehicle_name = cfg.get("vehicleName") or ""
    wifipass = cfg.get("wifipass") or ""

    # DHCP/static IP config
    ip_mode = cfg.get('ip_mode', 'dhcp')
    static_ip = cfg.get('static_ip', '')
    static_mask = cfg.get('static_mask', '')
    static_gw = cfg.get('static_gw', '')
    static_dns = cfg.get('static_dns', '')

    error_msg = ""
    if cfg.get("wifi_error"):
        error_msg = "<p style='color:red'>Error: Unable to connect using the saved WiFi credentials.</p>"

    # Status bar logic
    status_html = ""
    if status_info:
        if status_info.get('mode') == 'ap':
            status_html = "<div style='background:#f9e79f;color:#333;padding:8px 0 8px 0;margin-bottom:12px;border-radius:6px;font-weight:bold;'>AP Mode (no WiFi network configured)</div>"
        elif status_info.get('connected'):
            status_html = f"<div style='background:#c8e6c9;color:#256029;padding:8px 0 8px 0;margin-bottom:12px;border-radius:6px;font-weight:bold;'>Connected to: {status_info.get('ssid','?')}</div>"
        else:
            status_html = f"<div style='background:#ffcdd2;color:#b71c1c;padding:8px 0 8px 0;margin-bottom:12px;border-radius:6px;font-weight:bold;'>Not connected to WiFi</div>"

    # Scan results modal
    scan_modal = ""
    if scan_results is not None:
        scan_modal = """
        <div id='scan_modal' style='position:fixed;top:0;left:0;width:100vw;height:100vh;background:#0008;z-index:1000;display:flex;align-items:center;justify-content:center;'>
            <div style='background:#fff;padding:24px 32px;border-radius:10px;max-width:90vw;'>
                <h3>Select WiFi Network</h3>
                <ul style='list-style:none;padding:0;'>
        """
        for net in scan_results:
            ssid = net.get('ssid','')
            enc = '🔒' if net.get('secure') else ''
            scan_modal += f"<li style='margin-bottom:8px;'><button onclick=\"selectSSID('{ssid}')\" style='padding:4px 12px;'>{ssid} {enc}</button></li>"
        scan_modal += """
                </ul>
                <button onclick="closeScanModal()" style='margin-top:12px;'>Cancel</button>
            </div>
        </div>
        <script>
        function selectSSID(ssid) {
            document.getElementById('ssid_input').value = ssid;
            document.getElementById('wifipass_input').value = '';
            closeScanModal();
        }
        function closeScanModal() {
            document.getElementById('scan_modal').remove();
        }
        </script>
        """

    # Load header/nav HTML and inject vehicle_name
    try:
        with open("web/pages/assets/header_nav.html", "r") as f:
            header_nav = f.read().replace("{{ vehicle_name }}", vehicle_name)
    except Exception:
        header_nav = f"<div style='background:#222;color:#fff;padding:12px;text-align:center'>Rokenbok Vehicle Control<br><span style='color:#f9e79f'>{vehicle_name}</span></div>"

    return f"""
    <html>
    <body>
    {header_nav}
    <div style='max-width:600px;margin:32px auto 0 auto;'>
        <h2>WiFi Setup</h2>
        {status_html}
        {error_msg}
        <form method="POST" action="/wifi">
            <label>SSID:</label>
            <div style='display:flex;align-items:center;gap:8px;'>
                <input id="ssid_input" name="ssid" value="{ssid_val}" autocomplete="off">
                <button type="button" onclick="scanNetworks()">Scan</button>
            </div>
            <br>
            <label>Password:</label>
            <div style='display:flex;align-items:center;gap:8px;'>
                <input id="wifipass_input" name="wifipass" type="password" value="" autocomplete="off">
                <button type="button" onclick="toggleShowPW()" id="showpw_btn">👁️ Show</button>
            </div>
            <br>
            <label>IP Configuration:</label><br>
            <input type="radio" id="dhcp" name="ip_mode" value="dhcp" {'checked' if ip_mode=='dhcp' else ''} onchange="toggleStaticFields()"> <label for="dhcp">DHCP (Automatic)</label>
            <input type="radio" id="static" name="ip_mode" value="static" {'checked' if ip_mode=='static' else ''} onchange="toggleStaticFields()"> <label for="static">Static IP</label>
            <div id="static_fields" style="margin-top:8px;{'' if ip_mode=='static' else 'display:none;'}">
                <label>IP Address:</label><br>
                <input name="static_ip" value="{static_ip}" pattern="\d+\.\d+\.\d+\.\d+" autocomplete="off"><br>
                <label>Subnet Mask:</label><br>
                <input name="static_mask" value="{static_mask}" pattern="\d+\.\d+\.\d+\.\d+" autocomplete="off"><br>
                <label>Gateway:</label><br>
                <input name="static_gw" value="{static_gw}" pattern="\d+\.\d+\.\d+\.\d+" autocomplete="off"><br>
                <label>DNS:</label><br>
                <input name="static_dns" value="{static_dns}" pattern="\d+\.\d+\.\d+\.\d+" autocomplete="off"><br>
            </div>
            <br>
            <input type="submit" value="Save">
        </form>
    </div>
    {scan_modal}
    <script>
    function scanNetworks() {{
        fetch('/wifi_scan').then(r => r.json()).then(js => {{
            // Re-render page with scan results
            document.body.innerHTML += js.html;
        }});
    }}
    function toggleShowPW() {{
        var pw = document.getElementById('wifipass_input');
        var btn = document.getElementById('showpw_btn');
        if (pw.type === 'password') {{
            pw.type = 'text'; btn.textContent = '🙈 Hide';
        }} else {{
            pw.type = 'password'; btn.textContent = '👁️ Show';
        }}
    }}
    function toggleStaticFields() {{
        var staticFields = document.getElementById('static_fields');
        var staticRadio = document.getElementById('static');
        staticFields.style.display = staticRadio.checked ? '' : 'none';
    }}
    </script>
    </body>
    </html>
    """


# ---------------------------------------------------------
# GET Handler
# ---------------------------------------------------------

def handle_get():
    cfg = load_config()
    # Determine WiFi status
    status_info = {'mode': 'ap'}
    try:
        import network
        sta = network.WLAN(network.STA_IF)
        if sta.active() and sta.isconnected():
            status_info = {'connected': True, 'ssid': sta.config('essid')}
        else:
            status_info = {'connected': False, 'ssid': cfg.get('ssid') or ''}
    except Exception:
        pass
    html = build_wifi_page(cfg, status_info=status_info)
    return "200 OK", "text/html", html


# ---------------------------------------------------------
# POST Handler
# ---------------------------------------------------------

def xor_crypt(data, key):
    # Simple XOR encryption for MicroPython (not secure, but better than plain text)
    key = (key * ((len(data) // len(key)) + 1))[:len(data)]
    return bytes([a ^ b for a, b in zip(data, key)])

def handle_post(body, cfg):
    """
    body = raw POST body (URL-encoded string)
    cfg  = existing config dict (passed in by web_server)
    """

    # Parse POST fields
    fields = {}
    for pair in body.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            fields[k] = v.replace("+", " ")  # Basic decode

    ssid = fields.get("ssid", "")
    wifipass = fields.get("wifipass", "")
    ip_mode = fields.get("ip_mode", "dhcp")
    static_ip = fields.get("static_ip", "")
    static_mask = fields.get("static_mask", "")
    static_gw = fields.get("static_gw", "")
    static_dns = fields.get("static_dns", "")

    cfg["ssid"] = ssid
    cfg["ip_mode"] = ip_mode
    cfg["static_ip"] = static_ip
    cfg["static_mask"] = static_mask
    cfg["static_gw"] = static_gw
    cfg["static_dns"] = static_dns
    # Encrypt password before saving
    if wifipass:
        key = b"rokwifi1234"  # Simple static key; for real security use device-unique key
        enc = xor_crypt(wifipass.encode(), key)
        cfg["wifipass"] = ubinascii.b2a_base64(enc).decode().strip()
    else:
        cfg["wifipass"] = ""

    # Clear old failure marker
    cfg.pop("wifi_error", None)

    save_config(cfg)

    # Redirect to GET /wifi
    return cfg, "/wifi"
# --- WiFi scan endpoint ---
def handle_wifi_scan():
    nets = []
    try:
        import network
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        scan = sta.scan()
        for net in scan:
            ssid = net[0].decode() if isinstance(net[0], bytes) else str(net[0])
            secure = net[4] > 0
            nets.append({'ssid': ssid, 'secure': secure})
    except Exception as e:
        pass
    # Render only the modal
    html = build_wifi_page(load_config(), scan_results=nets)
    import ujson as json
    return "200 OK", "application/json", json.dumps({'html': html})
