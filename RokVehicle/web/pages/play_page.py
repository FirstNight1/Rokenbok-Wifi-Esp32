# pages/play_page.py

from RokCommon.variables.vars_store import get_config_value
from RokCommon.variables.vehicle_types import VEHICLE_TYPES
import json


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------


def get_vehicle_info():
    vtype = get_config_value("vehicleType")
    vehicle_name = get_config_value("vehicleName")
    info = next((v for v in VEHICLE_TYPES if v["typeName"] == vtype), None)
    return vtype, vehicle_name, info


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

    vtype, vehicle_name, info = get_vehicle_info()
    vehicle_name = vehicle_name or ""

    # Bluetooth scan endpoint
    if query_string and "bluetooth_scan" in query_string:
        from bluetooth_controller import controller
        import uasyncio as asyncio

        loop = asyncio.get_event_loop()
        devices = loop.run_until_complete(controller.scan(3000))
        # Return name/address for each device
        return (
            "200 OK",
            "application/json",
            json.dumps(
                {
                    "devices": [
                        {
                            "name": d["name"] or "Unknown",
                            "addr": d["addr"].hex(),
                            "addr_type": d["addr_type"],
                            "rssi": d["rssi"],
                        }
                        for d in devices
                    ]
                }
            ),
        )

    # Bluetooth pair endpoint
    if query_string and "bluetooth_pair" in query_string:
        from bluetooth_controller import controller
        import uasyncio as asyncio

        addr_hex = query_string.split("bluetooth_pair=")[1].split("&")[0]
        addr = bytes.fromhex(addr_hex)
        # For now, assume addr_type=0 (public)
        loop = asyncio.get_event_loop()
        ok = loop.run_until_complete(controller.pair(0, addr))
        return ("200 OK", "application/json", json.dumps({"success": ok}))

    # If ?config=1, return JSON config for JS (now includes mapping)
    if query_string and "config=1" in query_string:
        cam_cfg = get_config_value("camera_ips", {})
        area_ip = cam_cfg.get("area", "")
        fpv_ip = cam_cfg.get("fpv", "")
        view_mode = get_config_value("view_mode", "area")
        pip_flip = get_config_value("pip_flip", False)
        drive_mode = get_config_value("drive_mode", "tank")
        mapping = get_config_value("controller_mapping", {})
        # New: expose axis_motors, motor_functions, functions for dynamic mapping
        axis_motors = info["axis_motors"] if info and "axis_motors" in info else []
        motor_functions = (
            info["motor_functions"] if info and "motor_functions" in info else []
        )
        logic_functions = info["functions"] if info and "functions" in info else []
        # For legacy UI, keep aux_motors and all_motors for now
        aux_motors = [m for m in (motor_functions or [])]
        all_motors = list(axis_motors) + list(motor_functions)
        return (
            "200 OK",
            "application/json",
            json.dumps(
                {
                    "area_ip": area_ip,
                    "fpv_ip": fpv_ip,
                    "view_mode": view_mode,
                    "pip_flip": pip_flip,
                    "drive_mode": drive_mode,
                    "mapping": mapping,
                    "aux_motors": aux_motors,
                    "vehicle_type": vtype,
                    "motors": all_motors,
                    "axis_motors": axis_motors,
                    "motor_functions": motor_functions,
                    "logic_functions": logic_functions,
                }
            ),
        )

    # Load header/nav HTML and inject vehicle_name
    try:
        with open("web/pages/assets/header_nav.html", "r") as f:
            header_nav = f.read().replace("{{ vehicle_name }}", vehicle_name)
    except Exception:
        header_nav = f"<div style='background:#222;color:#fff;padding:12px;text-align:center'>Rokenbok Vehicle Control<br><span style='color:#f9e79f'>{vehicle_name}</span></div>"

    vehicle_type = vtype or "Unknown"
    vehicle_name = get_config_value("vehicleName", "Unnamed Vehicle")
    motors = info.get("motor_map", {}) if info else {}
    axis_map = {name: f"Axis {i+1}" for i, name in enumerate(motors.keys())}
    axis_map_list = "".join(
        [f"<li>{name}: {axis_map[name]}</li>" for name in motors.keys()]
    )
    cam_cfg = get_config_value("camera_ips", {})
    area_ip = cam_cfg.get("area", "")
    fpv_ip = cam_cfg.get("fpv", "")
    view_mode = get_config_value("view_mode", "area")
    pip_flip = get_config_value("pip_flip", False)
    drive_mode = get_config_value("drive_mode", "tank")

    # Load main HTML from asset file and inject values
    try:
        with open("web/pages/assets/play_page.html", "r") as f:
            html = f.read()
        html = html.replace("{{ header_nav }}", header_nav)
        html = html.replace("{{ vehicle_name }}", vehicle_name)
        html = html.replace("{{ vehicle_type }}", vehicle_type)
        html = html.replace("{{ axis_map_list }}", axis_map_list)
        html = html.replace("{{ area_ip }}", area_ip)
        html = html.replace("{{ fpv_ip }}", fpv_ip)
        # MicroPython str may not have capitalize()
        if drive_mode:
            drive_mode_cap = drive_mode[0].upper() + drive_mode[1:]
        else:
            drive_mode_cap = drive_mode
        html = html.replace("{{ drive_mode }}", drive_mode_cap)
    except Exception as e:
        html = f"<html><body><h2>Error loading play page: {e}</h2></body></html>"
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

    action = fields.get("action")

    # Save controller mapping (tank/dpad/aux, deadzone, reverse)
    if action == "save_mapping":
        # Expect fields: mapping (dict), drive_mode (str)
        mapping = fields.get("mapping", {})
        drive_mode = fields.get("drive_mode", "tank")
        from RokCommon.variables.vars_store import save_config_value

        save_config_value("controller_mapping", mapping)
        save_config_value("drive_mode", drive_mode)
        return (None, "/play")

    # Save camera/view config
    if action == "save_view":
        cam_cfg = get_config_value("camera_ips", {})
        area_ip = fields.get("area_ip")
        fpv_ip = fields.get("fpv_ip")
        if area_ip is not None:
            cam_cfg["area"] = area_ip
        if fpv_ip is not None:
            cam_cfg["fpv"] = fpv_ip
        from RokCommon.variables.vars_store import save_config_value

        save_config_value("camera_ips", cam_cfg)
        if "view_mode" in fields:
            save_config_value("view_mode", fields["view_mode"])
        if "pip_flip" in fields:
            save_config_value("pip_flip", bool(fields["pip_flip"]))
        return (None, "/play")

    # Return the updated config and redirect to play
    return (None, "/play")
