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


def handle_get():
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

    # Load header/nav HTML and inject vehicle_name
    try:
        with open("web/pages/assets/header_nav.html", "r") as f:
            header_nav = f.read().replace("{{ vehicle_name }}", vehicle_name)
    except Exception:
        header_nav = f"<div style='background:#222;color:#fff;padding:12px;text-align:center'>Rokenbok Vehicle Control<br><span style='color:#f9e79f'>{vehicle_name}</span></div>"

    html = f"""
<html>
<head>
  <title>Play Control</title>
  <style>
    body {{ font-family: Arial; margin: 16px; }}
    .placeholder {{
      max-width: 700px;
      margin: 64px auto 0 auto;
      padding: 48px;
      background: #f8f9fa;
      border-radius: 12px;
      text-align: center;
      color: #444;
      box-shadow: 0 2px 12px rgba(44,62,80,0.07);
    }}
    .placeholder h1 {{ font-size: 2.2em; margin-bottom: 18px; }}
    .placeholder p {{ font-size: 1.2em; }}
  </style>
</head>
<body>
  {header_nav}
  <div class="placeholder">
    <h1>Play Page Under Construction</h1>
    <p>This page will provide real-time vehicle control, gamepad mapping, and FPV streaming.<br><br>
    Check back soon for updates!</p>
  </div>
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

    if action == 'save_map':
        left = fields.get('left')
        right = fields.get('right')
        mode = fields.get('mode', 'tank')
        cfg['play_map'] = { 'left': left, 'right': right, 'mode': mode }
        save_config(cfg)

    # Return the updated config and redirect to play
    return (cfg, '/play')
