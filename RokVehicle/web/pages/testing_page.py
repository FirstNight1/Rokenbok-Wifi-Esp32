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

	# Build motor list from vehicle type
	motor_names = []
	if info:
		motor_names.extend(info.get("axis_motors", []))
		motor_names.extend(info.get("motor_functions", []))
	motor_min_cfg = cfg.get("motor_min", {})
	motor_reversed_cfg = cfg.get("motor_reversed", {})
	motor_html = ""
	for name in motor_names:
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

	# Load main HTML from asset file and inject values
	try:
		with open("web/pages/assets/testing_page.html", "r") as f:
			html = f.read()
		html = html.replace("{{ header_nav }}", header_nav)
		html = html.replace("{{ vtype }}", vtype)
		html = html.replace("{{ motor_html }}", motor_html)
	except Exception as e:
		html = f"<html><body><h2>Error loading testing page: {e}</h2></body></html>"

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

	# Handle config updates via POST only
	updated = False
	if action == 'save_min':
		name = fields.get('name')
		try:
			minv = int(fields.get('min', 40000))
		except Exception:
			minv = 40000
		mc.motor_controller.update_min_power(name, minv)
		updated = True
	elif action == 'save_reversed':
		name = fields.get('name')
		reversed_val = bool(fields.get('reversed', False))
		mc.motor_controller.update_reversed(name, reversed_val)
		updated = True
	# Reload config to reflect changes
	if updated:
		cfg = load_config()
		# Re-instantiate motor_controller to pick up new config
		import control.motor_controller as mc_mod
		mc_mod.motor_controller = mc_mod.MotorController()
	return (cfg, "/testing")
