from variables.vars_store import load_config, save_config
import sys
import os
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

    # Load WiFi page HTML template and inject values
    try:
        with open("web/pages/assets/header_nav.html", "r") as f:
            header_nav = f.read().replace("{{ vehicle_name }}", vehicle_name)
    except Exception:
        header_nav = f"<div style='background:#222;color:#fff;padding:12px;text-align:center'>Rokenbok Vehicle Control<br><span style='color:#f9e79f'>{vehicle_name}</span></div>"

    try:
        with open("web/pages/assets/wifi_page.html", "r") as f:
            html = f.read()
    except Exception:
        html = "<html><body><h2>WiFi page asset missing</h2></body></html>"

    # Prepare replacements for template
    html = html.replace("{{ header_nav }}", header_nav)
    html = html.replace("{{ status_html }}", status_html)
    html = html.replace("{{ error_msg }}", error_msg)
    html = html.replace("{{ ssid_val }}", ssid_val)
    html = html.replace("{{ vehicle_name }}", vehicle_name)
    # Ensure static_fields_display is always correct
    static_fields_display = '' if ip_mode == 'static' else 'display:none;'
    html = html.replace("{{ dhcp_checked }}", 'checked' if ip_mode=='dhcp' else '')
    html = html.replace("{{ static_checked }}", 'checked' if ip_mode=='static' else '')
    html = html.replace("{{ static_fields_display }}", static_fields_display)
    html = html.replace("{{ static_ip }}", static_ip)
    html = html.replace("{{ static_mask }}", static_mask)
    html = html.replace("{{ static_gw }}", static_gw)
    html = html.replace("{{ static_dns }}", static_dns)
    html = html.replace("{{ scan_modal }}", scan_modal)
    return html


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
    # Save password as plaintext (for simplicity)
    cfg["wifipass"] = wifipass

    # Clear old failure marker
    cfg.pop("wifi_error", None)

    save_config(cfg)

    # Redirect to GET /wifi
    return cfg, "/wifi"
# --- WiFi scan endpoint ---
def handle_wifi_scan():
    nets = []
    try:
        import network, utime
        sta = network.WLAN(network.STA_IF)
        sta.active(False)
        utime.sleep_ms(500)
        sta.active(True)
        utime.sleep_ms(500)
        scan = sta.scan()
        utime.sleep_ms(10)  # yield to scheduler
        seen = set()
        for net in scan:
            ssid = net[0].decode() if isinstance(net[0], bytes) else str(net[0])
            if ssid and ssid not in seen:
                secure = net[4] > 0
                nets.append({'ssid': ssid, 'secure': secure})
                seen.add(ssid)
    except Exception as e:
        pass
    # Render only the modal
    html = build_wifi_page(load_config(), scan_results=nets)
    import ujson as json
    return "200 OK", "application/json", json.dumps({'html': html})
