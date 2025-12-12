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
    # Determine which motors are axis and which are function
    axis_motors = set(info.get("axis_motors", [])) if info else set()
    function_motors = set(info.get("motor_functions", [])) if info else set()
    # Get current motor assignments and pin mapping
    import control.motor_controller as mc_mod

    assignments = mc_mod.motor_controller.get_motor_assignments()
    motor_nums_used = set()
    for name in motor_names:
        min_val = int(motor_min_cfg.get(name, 40000))
        min_scale = max(1, min(65, round(min_val / 1000)))
        reversed_val = bool(motor_reversed_cfg.get(name, False))
        is_function = name in function_motors
        motor_num = assignments.get(name, {}).get("motor_num", "?")
        pins = assignments.get(name, {}).get("pins", ("?", "?"))
        motor_nums_used.add(motor_num)
        # Dropdown for motor number selection (1-5, unique)
        options = "".join(
            [
                f'<option value="{i}"'
                + (" selected" if i == motor_num else "")
                + f">{i}</option>"
                for i in range(1, 6)
            ]
        )
        motor_html += (
            '<div class="motor-block">'
            f"<h3>{name}</h3>"
            f"<label>Motor Number:</label> <select id='{name}_motor_num'>{options}</select> "
            f"<button onclick='saveMotorNumbers()' style='margin-left:8px'>Save</button> "
            f"<span style='font-size:smaller'>(Pins: {pins[0]}, {pins[1]})</span><br>"
            f"<label>Duration (sec):</label>"
            f'<input id="{name}_duration" type="number" value="1" min="0" step="0.1"><br>'
            + (
                ""
                if is_function
                else (
                    f"<label>Power (0 - 100):</label>"
                    f'<input id="{name}_power" type="number" value="25" min="0" max="100"><br><br>'
                )
            )
            + (
                f"<label>{'Set Power' if is_function else 'Minimum Power'} (1-65):</label>"
                f'<input id="{name}_min" type="number" value="{min_scale}" min="1" max="65"> '
                f"<button onclick=\"saveMin('{name}')\">{'Save Set Power' if is_function else 'Save Minimum'}</button>"
                "<br>"
            )
            + f"<label>Reversed: <span id='{name}_reversed_val'>{str(reversed_val).lower()}</span></label>"
            + f"<button onclick=\"toggleReversed('{name}')\">Toggle Reversed</button>"
            + "<br><br>"
            + f"<button onclick=\"runMotor('{name}', 'fwd')\">Forward</button>"
            + f"<button onclick=\"runMotor('{name}', 'rev')\">Reverse</button>"
            + f"<button onclick=\"sendStop('{name}')\">Stop</button>"
            + "<br><br></div>"
        )

    # Load header/nav HTML and inject vehicle_name
    try:
        with open("web/pages/assets/header_nav.html", "r") as f:
            header_nav = f.read().replace("{{ vehicle_name }}", vehicle_name)
    except Exception:
        header_nav = f"<div style='background:#222;color:#fff;padding:12px;text-align:center'>Rokenbok Vehicle Control<br><span style='color:#f9e79f'>{vehicle_name}</span></div>"

    # Inject function motor list for JS
    function_motor_list = []
    if info:
        function_motor_list = info.get("motor_functions", [])
    function_motor_js = (
        f"<script>window.functionMotors = {json.dumps(function_motor_list)};</script>"
    )
    try:
        with open("web/pages/assets/testing_page.html", "r") as f:
            html = f.read()
        html = html.replace("{{ header_nav }}", header_nav)
        html = html.replace("{{ vtype }}", vtype)
        html = html.replace("{{ motor_html }}", motor_html)
        html = html.replace("</body>", function_motor_js + "</body>")
    except Exception as e:
        html = f"<html><body><h2>Error loading testing page: {e}</h2></body></html>"

    # MUST return (status, content_type, html)
    return ("200 OK", "text/html", html)


# ---------------------------------------------------------
# POST Handler
# ---------------------------------------------------------


def handle_post(body, cfg):

    try:
        fields = json.loads(body or "{}")
    except Exception:
        fields = {}

    action = fields.get("action")

    import control.motor_controller as mc

    # Handle config updates via POST only
    updated = False

    if action == "save_motor_numbers":
        # fields['assignments'] should be {name: motor_num}
        assignments = fields.get("assignments", {})
        # Convert keys to str, values to int
        try:
            assignments = {str(k): int(v) for k, v in assignments.items()}
        except Exception:
            return (cfg, f"/testing?error=Invalid+motor+number+assignment")
        import control.motor_controller as mc_mod

        try:
            mc_mod.motor_controller.set_motor_assignments(assignments)
            updated = True
        except Exception as e:
            return (cfg, f"/testing?error={str(e)}")

    if action == "save_min":
        name = fields.get("name")
        try:
            min_scale = int(fields.get("min", 40))
            minv = min(65, max(1, min_scale)) * 1000
        except Exception:
            minv = 40000
        # Directly update config
        cfg = load_config()
        mm = cfg.get("motor_min", {})
        if not isinstance(mm, dict):
            mm = {}
        mm[name] = minv
        cfg["motor_min"] = mm
        save_config(cfg)
        updated = True
    elif action == "toggle_reversed":
        name = fields.get("name")
        # Toggle the current value
        cfg = load_config()
        mr = cfg.get("motor_reversed", {})
        if not isinstance(mr, dict):
            mr = {}
        current = bool(mr.get(name, False))
        new_val = not current
        mr[name] = new_val
        cfg["motor_reversed"] = mr
        save_config(cfg)
        updated = True
    # Reload config to reflect changes
    if updated:
        cfg = load_config()
        # Re-instantiate motor_controller to pick up new config
        import control.motor_controller as mc_mod

        mc_mod.motor_controller = mc_mod.MotorController()
    return (cfg, "/testing")
