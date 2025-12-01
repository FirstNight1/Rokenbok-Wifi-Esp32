# pages/play_page.py

from variables.vars_store import load_config, save_config
from variables.vehicle_types import VEHICLE_TYPES
import json


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------


def get_vehicle_info():
    cfg = load_config()
    vtype = cfg.get("vehicleType")

    info = next((v for v in VEHICLE_TYPES if v["typeName"] == vtype), None)
    return cfg, vtype, info


# ---------------------------------------------------------
# GET Handler
# ---------------------------------------------------------


def handle_get(query_string=None):
    """Return a simple play page skeleton.

    This page is intentionally a lightweight skeleton. It exposes:
        - mode selector (tank / dpad)
        - mapping controls (select which motor is left/right)
        - a placeholder area for webcam/FPV
        - a Connect button that will open a WebSocket to send realtime commands

    The heavy gamepad mapping and streaming logic will be implemented later.
    """

    cfg, vtype, info = get_vehicle_info()
    vehicle_name = cfg.get("vehicleName") or ""


    # Bluetooth scan endpoint
    if query_string and 'bluetooth_scan' in query_string:
        from bluetooth_controller import controller
        import uasyncio as asyncio
        loop = asyncio.get_event_loop()
        devices = loop.run_until_complete(controller.scan(3000))
        # Return name/address for each device
        return ("200 OK", "application/json", json.dumps({
            'devices': [
                {'name': d['name'] or 'Unknown', 'addr': d['addr'].hex(), 'addr_type': d['addr_type'], 'rssi': d['rssi']} for d in devices
            ]
        }))

    # Bluetooth pair endpoint
    if query_string and 'bluetooth_pair' in query_string:
        from bluetooth_controller import controller
        import uasyncio as asyncio
        addr_hex = query_string.split('bluetooth_pair=')[1].split('&')[0]
        addr = bytes.fromhex(addr_hex)
        # For now, assume addr_type=0 (public)
        loop = asyncio.get_event_loop()
        ok = loop.run_until_complete(controller.pair(0, addr))
        return ("200 OK", "application/json", json.dumps({'success': ok}))

    # If ?config=1, return JSON config for JS (now includes mapping)
    if query_string and 'config=1' in query_string:
        cam_cfg = cfg.get('camera_ips', {})
        area_ip = cam_cfg.get('area', '')
        fpv_ip = cam_cfg.get('fpv', '')
        view_mode = cfg.get('view_mode', 'area')
        pip_flip = cfg.get('pip_flip', False)
        drive_mode = cfg.get('drive_mode', 'tank')
        mapping = cfg.get('controller_mapping', {})
        # New: expose axis_motors, motor_functions, functions for dynamic mapping
        axis_motors = info['axis_motors'] if info and 'axis_motors' in info else []
        motor_functions = info['motor_functions'] if info and 'motor_functions' in info else []
        logic_functions = info['functions'] if info and 'functions' in info else []
        # For legacy UI, keep aux_motors and all_motors for now
        aux_motors = [m for m in (motor_functions or [])]
        all_motors = list(axis_motors) + list(motor_functions)
        return ("200 OK", "application/json", json.dumps({
            'area_ip': area_ip,
            'fpv_ip': fpv_ip,
            'view_mode': view_mode,
            'pip_flip': pip_flip,
            'drive_mode': drive_mode,
            'mapping': mapping,
            'aux_motors': aux_motors,
            'vehicle_type': vtype,
            'motors': all_motors,
            'axis_motors': axis_motors,
            'motor_functions': motor_functions,
            'logic_functions': logic_functions
        }))

    # Load header/nav HTML and inject vehicle_name
    try:
        with open("web/pages/assets/header_nav.html", "r") as f:
            header_nav = f.read().replace("{{ vehicle_name }}", vehicle_name)
    except Exception:
        header_nav = f"<div style='background:#222;color:#fff;padding:12px;text-align:center'>Rokenbok Vehicle Control<br><span style='color:#f9e79f'>{vehicle_name}</span></div>"

    # --- Sidebar data ---
    vehicle_type = vtype or "Unknown"
    vehicle_name = cfg.get("vehicleName") or "Unnamed Vehicle"
    motors = info.get("motor_map", {}) if info else {}
    # Placeholder: axis mapping (to be implemented)
    axis_map = {name: f"Axis {i+1}" for i, name in enumerate(motors.keys())}
    # Camera IPs from config
    cam_cfg = cfg.get('camera_ips', {})
    area_ip = cam_cfg.get('area', '')
    fpv_ip = cam_cfg.get('fpv', '')
    view_mode = cfg.get('view_mode', 'area')
    pip_flip = cfg.get('pip_flip', False)

    html = f"""
<html>
<head>
  <title>Play Control</title>
  <style>
    body {{ font-family: Arial; margin: 0; background: #f8f9fa; }}
    .main-flex {{ display: flex; flex-direction: row; min-height: 100vh; }}
    .sidebar {{ width: 340px; background: #fff; border-left: 1px solid #ddd; padding: 24px 18px; box-shadow: -2px 0 8px rgba(44,62,80,0.04); display: flex; flex-direction: column; }}
    .sidebar h2 {{ font-size: 1.3em; margin-bottom: 8px; }}
    .sidebar .section {{ margin-bottom: 24px; }}
    .sidebar label {{ font-weight: 500; }}
    .sidebar input[type=text] {{ width: 80%; margin-bottom: 6px; }}
    .sidebar select, .sidebar button {{ margin-top: 6px; }}
    .sidebar .motor-map-list {{ font-size: 1em; margin: 0 0 8px 0; }}
    .sidebar .motor-map-list li {{ margin-bottom: 2px; }}
    .sidebar .view-btns button {{ margin-right: 8px; }}
    .sidebar .pip-flip-btn {{ margin-left: 12px; }}
    .sidebar .save-btn {{ margin-top: 8px; }}
    .sidebar .bt-section {{ border-top: 1px solid #eee; padding-top: 12px; }}
    .sidebar .bt-list {{ font-size: 0.98em; margin: 6px 0; }}
    .sidebar .bt-list li {{ margin-bottom: 2px; }}
    .sidebar .bt-status {{ font-size: 0.95em; color: #888; margin-top: 4px; }}
    .video-area {{ flex: 1; display: flex; align-items: center; justify-content: center; background: #222; position: relative; min-height: 100vh; }}
    .video-main, .video-pip {{ background: #000; border-radius: 8px; overflow: hidden; }}
    .video-main {{ position: absolute; top: 32px; left: 32px; width: 70vw; height: 70vh; z-index: 1; }}
    .video-pip {{ position: absolute; bottom: 32px; right: 32px; width: 22vw; height: 22vh; z-index: 2; border: 2px solid #fff; }}
    .video-main.flipped {{ left: unset; right: 32px; top: 32px; }}
    .video-pip.flipped {{ right: unset; left: 32px; bottom: 32px; }}
    .video-full {{ width: 90vw; height: 80vh; border-radius: 12px; background: #000; }}
    .video-label {{ position: absolute; left: 36px; top: 12px; color: #fff; font-size: 1.1em; z-index: 10; }}
  </style>
  <script src="/assets/play_page.js"></script>
</head>
<body>
  {header_nav}
  <div class="main-flex">
    <div class="video-area" id="video_area">
      <!-- Video rendering will be handled by JS -->
      <div id="video_container"></div>
    </div>
    <div class="sidebar">
      <div class="section">
        <h2>Vehicle Info</h2>
        <div><b>Name:</b> {vehicle_name}</div>
        <div><b>Type:</b> {vehicle_type}</div>
      </div>
      <div class="section">
        <h2>Motor Mapping</h2>
        <ul class="motor-map-list">
          {''.join([f'<li>{name}: {axis_map[name]}</li>' for name in motors.keys()])}
        </ul>
        <button id="toggle_mode_btn" onclick="toggleDriveMode()">Toggle D-Pad/Tank</button>
      </div>
      <div class="section">
        <h2>View Selection</h2>
        <div class="view-btns">
          <button onclick="setView('area')" id="view_area_btn">Area Camera</button>
          <button onclick="setView('fpv')" id="view_fpv_btn">FPV Camera</button>
          <button onclick="setView('pip')" id="view_pip_btn">Picture in Picture</button>
          <button onclick="flipPIP()" class="pip-flip-btn" id="flip_pip_btn">Flip PIP</button>
        </div>
        <div style="margin-top:10px">
          <label>Area Camera IP:</label><br>
          <input type="text" id="area_ip" value="{area_ip}" placeholder="e.g. 192.168.1.100">
          <br>
          <label>FPV Camera IP:</label><br>
          <input type="text" id="fpv_ip" value="{fpv_ip}" placeholder="e.g. 192.168.1.101">
          <br>
          <button class="save-btn" onclick="saveCameraIPs()">Save Camera IPs</button>
        </div>
      </div>
      <div class="section bt-section">
        <h2>Controller</h2>
        <div id="controller_source_section"></div>
        <div id="ble_controller_section">
          <button onclick="scanBT()">Scan for Controllers</button>
          <ul class="bt-list" id="bt_list"></ul>
          <div class="bt-status" id="bt_status">Not connected</div>
        </div>
        <div id="browser_controller_section" style="display:none;margin-top:10px;"></div>
      </div>
    </div>
  </div>
  <script>
    // Placeholder JS hooks for view selection, camera IPs, PIP flip, BT scan
    function setView(mode) {{ /* TODO: implement view switching */ }}
    function flipPIP() {{ /* TODO: implement PIP flip */ }}
    function saveCameraIPs() {{ /* TODO: implement save camera IPs */ }}
    function scanBT() {{ /* TODO: implement BT scan */ }}
    function toggleDriveMode() {{ /* TODO: implement D-Pad/Tank toggle */ }}
  </script>
</body>
</html>
"""

    return ("200 OK", "text/html", html)


# ---------------------------------------------------------
# POST Handler
# ---------------------------------------------------------


def handle_post(body, cfg):
  """Accepts a small JSON body to save mapping choices.

  Expected JSON: { action: 'save_map', left: 'left', right: 'right', mode: 'tank' }
  For now we persist into cfg['play_map'] as a convenience.
  """
  try:
    fields = json.loads(body or "{}")
  except Exception:
    fields = {}

  action = fields.get('action')

  # Save controller mapping (tank/dpad/aux, deadzone, reverse)
  if action == 'save_mapping':
    # Expect fields: mapping (dict), drive_mode (str)
    mapping = fields.get('mapping', {})
    drive_mode = fields.get('drive_mode', 'tank')
    cfg['controller_mapping'] = mapping
    cfg['drive_mode'] = drive_mode
    save_config(cfg)
    return (cfg, '/play')

  # Save camera/view config
  if action == 'save_view':
    cam_cfg = cfg.get('camera_ips', {})
    area_ip = fields.get('area_ip')
    fpv_ip = fields.get('fpv_ip')
    if area_ip is not None:
      cam_cfg['area'] = area_ip
    if fpv_ip is not None:
      cam_cfg['fpv'] = fpv_ip
    cfg['camera_ips'] = cam_cfg
    if 'view_mode' in fields:
      cfg['view_mode'] = fields['view_mode']
    if 'pip_flip' in fields:
      cfg['pip_flip'] = bool(fields['pip_flip'])
    save_config(cfg)
    return (cfg, '/play')

  # Return the updated config and redirect to play
  return (cfg, '/play')
