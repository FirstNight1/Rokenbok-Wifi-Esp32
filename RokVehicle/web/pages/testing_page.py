# pages/testing_page.py

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
	cfg, vtype, info = get_vehicle_info()
	vehicle_name = cfg.get("vehicleName") or ""

	# Build motor control HTML dynamically
	motors = info.get("motor_map", {}) if info else {}
	motor_min_cfg = cfg.get("motor_min", {})
	motor_reversed_cfg = cfg.get("motor_reversed", {})
	motor_html = ""
	for name in motors.keys():
		min_val = motor_min_cfg.get(name, 40000)
		reversed_val = motor_reversed_cfg.get(name, False)
		checked = "checked" if reversed_val else ""
		motor_html += (
			"<div class=\"motor-block\">"
			f"<h3>{name}</h3>"
			f"<label>Duration (sec):</label>"
			f"<input id=\"{name}_duration\" type=\"number\" value=\"1\" min=\"0\" step=\"0.1\"><br>"
			f"<label>Power (0 - 100):</label>"
			f"<input id=\"{name}_power\" type=\"number\" value=\"25\" min=\"0\" max=\"100\"><br><br>"
			f"<label>Min Power (duty_u16):</label>"
			f"<input id=\"{name}_min\" type=\"number\" value=\"{min_val}\" min=\"0\" max=\"65535\"><br>"
			f"<button onclick=\"saveMin('{name}')\">Save Min</button>"
			"<br>"
			f"<label>Reversed:</label>"
			f"<input type=\"checkbox\" id=\"{name}_reversed\" {'checked' if reversed_val else ''} >"
			f"<button onclick=\"saveReversed('{name}')\">Save Reversed</button>"
			"<br><br>"
			f"<button onclick=\"runMotor('{name}', 'fwd')\">Forward</button>"
			f"<button onclick=\"runMotor('{name}', 'rev')\">Reverse</button>"
			f"<button onclick=\"sendStop('{name}')\">Stop</button>"
			"<br><br></div>"
		)

	# Load header/nav HTML and inject vehicle_name
	try:
		with open("web/pages/assets/header_nav.html", "r") as f:
			header_nav = f.read().replace("{{ vehicle_name }}", vehicle_name)
	except Exception:
		header_nav = f"<div style='background:#222;color:#fff;padding:12px;text-align:center'>Rokenbok Vehicle Control<br><span style='color:#f9e79f'>{vehicle_name}</span></div>"

	html = f"""
<html>
<head>
	<title>Motor Testing</title>
	<style>
		body {{
			font-family: Arial;
			margin: 20px;
		}}
		.motor-block {{
			border: 1px solid #ccc;
			padding: 15px;
			margin-bottom: 15px;
			border-radius: 8px;
		}}
		button {{
			margin: 4px;
			padding: 8px 14px;
		}}
		#stopAll {{
			background-color: red;
			color: white;
			padding: 12px 22px;
			font-size: 16px;
		}}
	</style>
	<script src="/assets/testing_page.js"></script>
</head>
<body>
	{header_nav}
	<div style='max-width:700px;margin:32px auto 0 auto;'>
	  <h2>Motor Testing</h2>
	  <h3>Current Vehicle Type: <span style=\"color: blue;\">{vtype}</span></h3>
	  <p>If this is incorrect, visit the <a href="/admin">Admin Page</a>.</p>
	  <hr>
	  <h3>Motors</h3>
	  {motor_html}
	  <br>
	  <div>
		<button id="stopAll" class="stop-btn" onclick="stopAll()">STOP ALL MOTORS</button>
		<span id="ws_status" style="margin-left:16px;color:red">WebSocket: Disconnected</span>
	  </div>
	</div>
</body>
</html>
"""

	# MUST return (status, content_type, html)
	return ("200 OK", "text/html", html)


# ---------------------------------------------------------
# POST Handler
# ---------------------------------------------------------


def handle_post(body, cfg):
	"""
	Must return (new_cfg, redirect_path)
	"""
	try:
		fields = json.loads(body or "{}")
	except Exception:
		fields = {}

	action = fields.get("action")

	import control.motor_controller as mc

	# Debug: log any non-save_min POSTs so we can trace old clients still POSTing
	if action and action != 'save_min':
		try:
			print("Ignored POST to /testing - action:", action, "body:", fields)
		except Exception:
			pass

	# Save per-motor minimum
	if action == 'save_min':
		name = fields.get('name')
		try:
			minv = int(fields.get('min', 40000))
		except Exception:
			minv = 40000
		mc.motor_controller.update_min_power(name, minv)

	# Save per-motor reversed
	if action == 'save_reversed':
		name = fields.get('name')
		val = bool(fields.get('reversed', False))
		if 'motor_reversed' not in cfg:
			cfg['motor_reversed'] = {}
		cfg['motor_reversed'][name] = val
		save_config(cfg)

	# Direct stop_all request
	# Only 'save_min' is supported via POST for this page. All realtime
	# motor control (set/stop/stop_all) is handled over WebSocket and any
	# POSTs for those actions are ignored.

	# For this page, config is unchanged; redirect back to testing
	return (cfg, "/testing")
