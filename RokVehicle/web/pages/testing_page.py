# pages/testing_page.py

from RokCommon.web.request_response import Response
from RokCommon.variables.vars_store import get_config_value, save_config_value, load_config, save_config
from RokCommon.variables.vehicle_types import VEHICLE_TYPES
from RokCommon.web.pages.home_page import load_and_process_header
import json


def _build_axis_motor_config():
    """Build axis motor configuration HTML"""
    # Get current vehicle type and motor configuration
    vtype = get_config_value("vehicleType")
    vinfo = next((v for v in VEHICLE_TYPES if v["typeName"] == vtype), None)
    if not vinfo:
        return ""
    
    axis_motors = vinfo.get("axis_motors", [])
    if not axis_motors:
        return "<p>No drive motors configured for this vehicle type.</p>"
    
    # Get current config values
    motor_min_cfg = get_config_value("motor_min", {})
    motor_slow_cfg = get_config_value("motor_slow", {})
    motor_max_cfg = get_config_value("motor_max", {})
    
    html = []
    for motor_name in axis_motors:
        min_val = motor_min_cfg.get(motor_name, 40000) // 1000  # Convert to 1-65 range
        slow_val = motor_slow_cfg.get(motor_name, 50000) // 1000
        max_val = motor_max_cfg.get(motor_name, 65535)
        # Handle max value display (65535 -> 65)
        max_display = 65 if max_val >= 65535 else max_val // 1000
        
        html.append(f"""
        <div style="margin-bottom: 15px; padding: 10px; border: 1px solid #ddd; border-radius: 3px;">
            <h5 style="margin: 0 0 10px 0; color: #444;">{str(motor_name)[0].upper() + str(motor_name)[1:] if len(str(motor_name)) > 0 else str(motor_name)} Motor</h5>
            <div style="display: flex; gap: 15px; flex-wrap: wrap; align-items: center;">
                <div>
                    <label>Min Power (1-65):</label><br>
                    <input type="number" name="{motor_name}_min" value="{min_val}" min="1" max="65" style="width: 60px;">
                </div>
                <div>
                    <label>Slow Power (1-65):</label><br>
                    <input type="number" name="{motor_name}_slow" value="{slow_val}" min="1" max="65" style="width: 60px;">
                </div>
                <div>
                    <label>Max Power (1-65):</label><br>
                    <div style="display: flex; gap: 5px; align-items: center;">
                        <input type="number" name="{motor_name}_max" value="{max_display}" min="1" max="65" style="width: 60px;">
                        <button type="button" onclick="setMaxPower('{motor_name}')" style="padding: 2px 8px; font-size: 12px;">Max</button>
                    </div>
                </div>
            </div>
        </div>""")
    
    return "".join(html)


def _build_function_motor_config():
    """Build function motor configuration HTML"""
    # Function motor configuration is now handled inline in the main motor list
    # This function is kept for compatibility but returns empty
    return ""


class TestingHandler:
    """Testing page handler using unified Request/Response system"""

    def handle_get(self, request):
        """Handle GET requests for testing page"""
        try:
            result = handle_get_legacy()
            if isinstance(result, tuple) and len(result) == 3:
                status, content_type, html = result
                return Response(status=status, content_type=content_type, body=html)
            else:
                return Response.html(str(result))
        except Exception as e:
            print(f"Testing page GET error: {e}")
            return Response.server_error(f"Error loading testing page: {str(e)}")

    def handle_post(self, request):
        """Handle POST requests for testing page"""
        try:
            cfg = load_config()
            result = handle_post_legacy(request.body, cfg)
            if isinstance(result, tuple) and len(result) == 2:
                # Handle redirect response
                updated_cfg, redirect_path = result
                if updated_cfg:
                    save_config(updated_cfg)
                return Response.redirect_to(redirect_path)
            else:
                return Response.json({"status": "ok"})
        except Exception as e:
            print(f"Testing page POST error: {e}")
            return Response.server_error(f"Error processing testing request: {str(e)}")


# Create handler instance
testing_handler = TestingHandler()


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


def handle_get_legacy():
    vtype, vehicle_name, info = get_vehicle_info()
    vehicle_name = vehicle_name or ""

    # Build motor list from vehicle type
    motor_names = []
    if info:
        motor_names.extend(info.get("axis_motors", []))
        motor_names.extend(info.get("motor_functions", []))
    motor_min_cfg = get_config_value("motor_min", {})
    motor_reversed_cfg = get_config_value("motor_reversed", {})
    motor_slow_cfg = get_config_value("motor_slow", {})
    motor_max_cfg = get_config_value("motor_max", {})
    motor_html = ""
    # Determine which motors are axis and which are function
    axis_motors = set(info.get("axis_motors", [])) if info else set()
    function_motors = set(info.get("motor_functions", [])) if info else set()
    # Get current motor assignments and pin mapping
    import control.motor_controller as mc_mod

    assignments = mc_mod.motor_controller.get_motor_assignments()
    motor_nums_used = set()
    axis_motor_count = 0
    for i, name in enumerate(motor_names):
        min_val = int(motor_min_cfg.get(name, 40000))
        min_scale = max(1, min(65, round(min_val / 1000)))
        reversed_val = bool(motor_reversed_cfg.get(name, False))
        is_function = name in function_motors
        is_axis = name in axis_motors
        motor_num = assignments.get(name, {}).get("motor_num", "?")
        pins = assignments.get(name, {}).get("pins", ("?", "?"))
        motor_nums_used.add(motor_num)
        
        if is_axis:
            axis_motor_count += 1
        
        # Dropdown for motor number selection (1-5, unique)
        options = "".join(
            [
                f'<option value="{i}"'
                + (" selected" if i == motor_num else "")
                + f">{i}</option>"
                for i in range(1, 6)
            ]
        )
        
        # Add power configuration inline for axis motors
        power_config_html = ""
        inline_power_html = ""
        function_config_html = ""
        
        if is_axis:
            slow_val = motor_slow_cfg.get(name, 50000) // 1000
            max_val = motor_max_cfg.get(name, 65535)
            max_display = 65 if max_val >= 65535 else max_val // 1000
            inline_power_html = f'''
            <div class="power-config" style="margin: 10px 0; padding: 10px; background: #f5f5f5; border-radius: 5px;">
                <h4 style="margin: 0 0 10px 0; color: #444; font-size: 14px;">Power Settings (0-65)</h4>
                <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
                    <div style="flex: 1; min-width: 80px;">
                        <label style="font-size: 12px; color: #666;">Min Power:</label><br>
                        <input type="number" id="{name}_min" value="{min_scale}" min="1" max="65" style="width: 60px; padding: 4px;">
                    </div>
                    <div style="flex: 1; min-width: 80px;">
                        <label style="font-size: 12px; color: #666;">Slow Power:</label><br>
                        <input type="number" id="{name}_slow" value="{slow_val}" min="1" max="65" style="width: 60px; padding: 4px;">
                    </div>
                    <div style="flex: 1; min-width: 80px;">
                        <label style="font-size: 12px; color: #666;">Max Power:</label><br>
                        <div style="display: flex; gap: 5px; align-items: center;">
                            <input type="number" id="{name}_max" value="{max_display}" min="1" max="65" style="width: 60px; padding: 4px;">
                            <button type="button" onclick="setMaxPower('{name}')" style="padding: 2px 6px; font-size: 11px;">Max</button>
                        </div>
                    </div>
                    <div style="flex: 1; min-width: 120px;">
                        <button type="button" onclick="saveMotorPowerSettings('{name}')" style="padding: 6px 12px; font-size: 12px; background: #3498db; color: white; border: none; border-radius: 3px; cursor: pointer;">Save Settings</button>
                    </div>
                </div>
            </div>
            '''
        elif is_function:
            # Function motor configuration integrated inline
            safety_enabled = get_config_value("motor_travel_safety_enabled", {}).get(name, False)
            forward_limit = get_config_value("motor_travel_safety_forward", {}).get(name, 0.0)
            reverse_limit = get_config_value("motor_travel_safety_reverse", {}).get(name, 0.0)
            
            function_config_html = f'''
            <div class="function-config" style="margin: 10px 0; padding: 10px; background: #f0f8ff; border-radius: 5px;">
                <h4 style="margin: 0 0 10px 0; color: #444; font-size: 14px;">Function Settings</h4>
                <div style="display: flex; gap: 15px; flex-wrap: wrap; align-items: start;">
                    <div>
                        <label style="font-size: 12px; color: #666;">Set Power (1-65):</label><br>
                        <input type="number" id="{name}_min" value="{min_scale}" min="1" max="65" style="width: 60px; padding: 4px;">
                    </div>
                    <div>
                        <label style="display: flex; align-items: center; font-size: 12px;">
                            <input type="checkbox" id="{name}_travel_safety" {"checked" if safety_enabled else ""} style="margin-right: 5px;">
                            Travel Safety Limits
                        </label>
                        <div style="display: flex; gap: 10px; margin-top: 5px;">
                            <div>
                                <label style="font-size: 11px; color: #666;">Forward (sec):</label><br>
                                <input type="number" id="{name}_forward_limit" value="{forward_limit}" min="0" max="60" step="0.1" style="width: 60px; padding: 2px; font-size: 11px;">
                            </div>
                            <div>
                                <label style="font-size: 11px; color: #666;">Reverse (sec):</label><br>
                                <input type="number" id="{name}_reverse_limit" value="{reverse_limit}" min="0" max="60" step="0.1" style="width: 60px; padding: 2px; font-size: 11px;">
                            </div>
                        </div>
                    </div>
                    <div>
                        <button type="button" onclick="saveFunctionSettings('{name}')" style="padding: 6px 12px; font-size: 12px; background: #27ae60; color: white; border: none; border-radius: 3px; cursor: pointer; margin-top: 15px;">Save Settings</button>
                    </div>
                </div>
                <small style="color: #888; font-style: italic;">Note: Travel safety changes require restart to take effect</small>
            </div>
            '''
        
        motor_html += (
            '<div class="motor-block" style="border: 2px solid #ddd; padding: 15px; margin-bottom: 20px; border-radius: 8px; background: #fafafa;">'
            f"<h3 style='margin: 0 0 15px 0; color: #2c3e50; border-bottom: 1px solid #ddd; padding-bottom: 8px;'>{name}</h3>"
            f"<div style='display: flex; gap: 15px; flex-wrap: wrap; align-items: center; margin-bottom: 15px;'>"
            f"<div><label style='font-size: 12px; color: #666;'>Motor Number:</label><br><select id='{name}_motor_num' style='padding: 4px;'>{options}</select></div>"
            f"<div><button onclick='saveMotorNumbers()' style='padding: 5px 10px; font-size: 12px; background: #3498db; color: white; border: none; border-radius: 3px;'>Save</button></div>"
            f"<div><span style='font-size: 11px; color: #888;'>Pins: {pins[0]}, {pins[1]}</span></div>"
            f"</div>"
            + inline_power_html
            + function_config_html
            + f"<div style='margin: 15px 0; padding: 10px; background: #f9f9f9; border-radius: 5px;'>"
            + f"<h4 style='margin: 0 0 10px 0; color: #444; font-size: 14px;'>Motor Control</h4>"
            + f"<div style='display: flex; gap: 15px; flex-wrap: wrap; align-items: center;'>"
            + f"<div><label style='font-size: 12px; color: #666;'>Duration (sec):</label><br>"
            + f'<input id="{name}_duration" type="number" value="1" min="0" step="0.1" style="width: 80px; padding: 4px;"></div>'
            + (
                f"<div><label style='font-size: 12px; color: #666;'>Run Power:</label><br>"
                + f'<select id="{name}_power_mode" style="padding: 4px;">'
                + f'<option value="min">Min Power</option>'
                + f'<option value="slow">Slow Power</option>'
                + f'<option value="max" selected>Max Power</option>'
                + f'</select></div>'
                if not is_function
                else ""
            )
            + f"<div><label style='font-size: 12px; color: #666;'>Reversed:</label><br>"
            + f"<span id='{name}_reversed_val' style='padding: 4px 8px; background: {'#e74c3c' if reversed_val else '#27ae60'}; color: white; border-radius: 3px; font-size: 11px;'>{'Yes' if reversed_val else 'No'}</span> "
            + f"<button onclick=\"toggleReversed('{name}')\" style='padding: 3px 8px; font-size: 11px; margin-left: 5px;'>Toggle</button></div>"
            + f"</div>"
            + f"<div style='margin-top: 15px; display: flex; gap: 10px;'>"
            + f"<button onclick=\"runMotor('{name}', 'fwd')\" style='padding: 8px 16px; background: #27ae60; color: white; border: none; border-radius: 4px; font-weight: bold;'>Forward</button>"
            + f"<button onclick=\"runMotor('{name}', 'rev')\" style='padding: 8px 16px; background: #e67e22; color: white; border: none; border-radius: 4px; font-weight: bold;'>Reverse</button>"
            + f"<button onclick=\"sendStop('{name}')\" style='padding: 8px 16px; background: #e74c3c; color: white; border: none; border-radius: 4px; font-weight: bold;'>Stop</button>"
            + f"</div></div>"
            + "</div>"
        )
        
        # Add tracking adjustment after first axis motor if there are exactly 2 axis motors
        if is_axis and axis_motor_count == 1 and len(axis_motors) == 2:
            tracking_adjustment = get_config_value("drive_tracking_adjustment", 0.0)
            
            # Get axis motor names for sync functionality
            axis_motor_names = list(axis_motors)
            
            # Determine arrow display based on current value
            arrow_display = "->" if tracking_adjustment == 0.0 else ("/" if tracking_adjustment > 0 else "\\")
            
            motor_html += f'''
            <div style="margin: 20px 0; padding: 20px; border: 2px dashed #3498db; background: #ecf0f1; border-radius: 8px;">
                <h3 style="color: #2c3e50; margin: 0 0 10px 0;">Drive Tracking Adjustment</h3>
                <p style="color: #666; margin: 0 0 15px 0;">Adjust motor power balance to correct if the vehicle doesn't track straight. If the vehicle drifts to one side, adjust in the opposite direction.</p>
                <form method="POST" action="/testing">
                    <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 15px 0;">
                        <button type="button" id="trackVeryLeft" style="padding: 8px 12px; background: #e74c3c; color: white; border: none; border-radius: 4px; font-size: 12px;">
                            <<< -2.0%
                        </button>
                        <button type="button" id="trackLeft" style="padding: 8px 12px; background: #f39c12; color: white; border: none; border-radius: 4px; font-size: 12px;">
                            < -0.2%
                        </button>
                        <div style="display: flex; align-items: center; gap: 8px; min-width: 120px; background: white; padding: 8px; border-radius: 4px; border: 1px solid #ccc;">
                            <input type="text" id="trackingValue" value="{tracking_adjustment}" 
                                   style="width: 50px; text-align: center; border: none; font-weight: bold;" readonly>
                            <span style="font-size: 12px; color: #666;">%</span>
                            <span id="trackingArrow" style="font-size: 16px; color: #3498db;">{arrow_display}</span>
                        </div>
                        <button type="button" id="trackZero" style="padding: 8px 12px; background: #95a5a6; color: white; border: none; border-radius: 4px; font-size: 12px;">
                            0%
                        </button>
                        <button type="button" id="trackRight" style="padding: 8px 12px; background: #f39c12; color: white; border: none; border-radius: 4px; font-size: 12px;">
                            +0.2% >
                        </button>
                        <button type="button" id="trackVeryRight" style="padding: 8px 12px; background: #e74c3c; color: white; border: none; border-radius: 4px; font-size: 12px;">
                            +2.0% >>>
                        </button>
                    </div>
                    <input type="hidden" name="driveTrackingAdjustment" id="driveTrackingAdjustment" value="{tracking_adjustment}">
                    <div style="margin: 15px 0; display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                        <button type="submit" name="save_tracking" value="1" style="padding: 10px 20px; background: #3498db; color: white; border: none; border-radius: 4px; font-weight: bold;">Save Tracking Adjustment</button>
                        <button type="button" id="testDrive" style="padding: 10px 20px; background: #27ae60; color: white; border: none; border-radius: 4px; font-weight: bold;">Test Drive Forward (10s)</button>
                        <button type="button" id="stopDrive" style="padding: 8px 16px; background: #e74c3c; color: white; border: none; border-radius: 4px; font-weight: bold;">STOP</button>
                    </div>
                </form>
                
                <div style="margin-top: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; background: #f9f9f9;">
                    <h4 style="color: #2c3e50; margin: 0 0 10px 0;">Power Sync Controls</h4>
                    <p style="color: #666; font-size: 13px; margin: 0 0 10px 0;">Copy power settings between drive motors for consistency.</p>
                    <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                        <button type="button" onclick="syncPowerSettings('{axis_motor_names[0]}', '{axis_motor_names[1]}')" 
                                style="padding: 8px 12px; background: #9b59b6; color: white; border: none; border-radius: 4px; font-size: 12px;">
                            Copy {axis_motor_names[0][0].upper() + axis_motor_names[0][1:] if len(axis_motor_names[0]) > 0 else axis_motor_names[0]} -> {axis_motor_names[1][0].upper() + axis_motor_names[1][1:] if len(axis_motor_names[1]) > 0 else axis_motor_names[1]}
                        </button>
                        <button type="button" onclick="syncPowerSettings('{axis_motor_names[1]}', '{axis_motor_names[0]}')" 
                                style="padding: 8px 12px; background: #9b59b6; color: white; border: none; border-radius: 4px; font-size: 12px;">
                            Copy {axis_motor_names[1][0].upper() + axis_motor_names[1][1:] if len(axis_motor_names[1]) > 0 else axis_motor_names[1]} -> {axis_motor_names[0][0].upper() + axis_motor_names[0][1:] if len(axis_motor_names[0]) > 0 else axis_motor_names[0]}
                        </button>
                    </div>
                </div>
            </div>
            '''

    # Load header/nav HTML and inject vehicle_name
    try:
        # Load header navigation using shared function
        header_nav = load_and_process_header(vehicle_name)
        if not header_nav:
            header_nav = "<div>Header not found</div>"
    except Exception as e:
        print(f"Header loading error: {e}")
        header_nav = "<div>Header not found</div>"

    # Inject function motor list for JS
    function_motor_list = []
    if info:
        function_motor_list = info.get("motor_functions", [])
    function_motor_js = (
        f"<script>window.functionMotors = {json.dumps(function_motor_list)};</script>"
    )
    try:
        # Load template helper function
        def _load_template(path):
            """Load template with fallback paths"""
            from RokCommon.web.static_assets import load_template

            # For project-specific templates, try relative path first
            if (
                "admin_page.html" in path
                or "testing_page.html" in path
                or "play_page.html" in path
            ):
                content = load_template(path)
                if content is not None:
                    return content
                # Don't try RokCommon path for project-specific templates
                return None

            # For common templates, try RokCommon path first
            content = load_template(f"RokCommon/{path}")
            if content is not None:
                return content
            # Fallback to relative path
            content = load_template(path)
            if content is not None:
                return content
            return None

        html = _load_template("web/pages/assets/testing_page.html")
        if html is None:
            raise Exception("Testing page template is None")
        
        # Add JavaScript motor data injection
        axis_motors_list = list(axis_motors) if axis_motors else []
        function_motors_list = list(function_motors) if function_motors else []
        motor_data_js = f'''
        <script>
        window.axisMotors = {axis_motors_list};
        window.functionMotors = {function_motors_list};
        </script>
        '''
        
        html = html.replace("{{ header_nav }}", header_nav or "")
        html = html.replace("{{ vtype }}", vtype or "")
        html = html.replace("{{ motor_html }}", motor_html or "")
        html = html.replace("</body>", motor_data_js + function_motor_js + "</body>")
    except Exception as e:
        html = f"<html><body><h2>Error loading testing page: {e}</h2><p>vehicle_name: {vehicle_name}</p><p>vtype: {vtype}</p></body></html>"

    # MUST return (status, content_type, html)
    return ("200 OK", "text/html", html)


# ---------------------------------------------------------
# POST Handler
# ---------------------------------------------------------


def handle_post_legacy(body, cfg):
    # Initialize updated flag first
    updated = False

    # Try JSON parsing first, then fall back to form parsing
    try:
        fields = json.loads(body or "{}")
    except Exception:
        # Try URL form parsing for form submissions using simple parsing
        try:
            if body and isinstance(body, (str, bytes)):
                if isinstance(body, bytes):
                    body = body.decode('utf-8')
                fields = {}
                # Simple form parsing for MicroPython
                pairs = body.split('&')
                for pair in pairs:
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        # Simple URL decode (replace + with space, basic %XX decoding)
                        key = key.replace('+', ' ')
                        value = value.replace('+', ' ')
                        # Basic percent decoding for common cases
                        if '%' in value:
                            value = value.replace('%2B', '+').replace('%3D', '=').replace('%26', '&')
                        fields[key] = value
        except Exception as e:
            fields = {}

    action = fields.get("action")

    import control.motor_controller as mc

    if "save_tracking" in fields:
        # Save drive tracking adjustment
        try:
            tracking_val = float(fields.get("driveTrackingAdjustment", 0.0))
            
            # Save the value
            save_config_value("drive_tracking_adjustment", tracking_val)
            
            print(f"Drive tracking adjustment saved: {tracking_val}%")
            
            # Important: Don't set updated=True to avoid motor controller reinitialization
            # which could reload default config values
        except Exception as e:
            print(f"ERROR saving tracking adjustment: {e}")
            import sys
            sys.print_exception(e)
            # Don't save 0.0 on error - let user know there was a problem
        
        # Simple redirect without query parameter to avoid issues
        return (cfg, "/testing")

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

        mm = get_config_value("motor_min", {})
        if not isinstance(mm, dict):
            mm = {}
        mm[name] = minv
        save_config_value("motor_min", mm)
        updated = True
    elif action == "toggle_reversed":
        name = fields.get("name")
        # Toggle the current value

        mr = get_config_value("motor_reversed", {})
        if not isinstance(mr, dict):
            mr = {}
        current = bool(mr.get(name, False))
        new_val = not current
        mr[name] = new_val
        save_config_value("motor_reversed", mr)
        
        # Reinitialize motor controller to apply reversed setting immediately
        try:
            import control.motor_controller as mc
            # Use in-place reinitialization to pick up new reversed setting
            mc.motor_controller.reload_config_and_reinit()
            print(f"Motor controller reinitialized for reversed toggle: {name} = {new_val}")
        except Exception as e:
            print(f"Error reinitializing motor controller: {e}")
        
        updated = True
        
    elif action == "save_axis_config":
        # Save axis motor power configuration (min/slow/max)
        name = fields.get("name")
        
        try:
            min_power = int(fields.get("min_power", 40))
            slow_power = int(fields.get("slow_power", 50))
            max_power = int(fields.get("max_power", 65))
            
            # Clamp values to valid range
            min_power = min(65, max(1, min_power))
            slow_power = min(65, max(1, slow_power))
            max_power = min(65, max(1, max_power))
            
            # Convert to internal scale (multiply by 1000)
            min_val = min_power * 1000
            slow_val = slow_power * 1000
            max_val = max_power * 1000 if max_power < 65 else 65535
            
            # Update motor_min config
            mm = get_config_value("motor_min", {})
            if not isinstance(mm, dict):
                mm = {}
            mm[name] = min_val
            save_config_value("motor_min", mm)
            
            # Update motor_slow config
            ms = get_config_value("motor_slow", {})
            if not isinstance(ms, dict):
                ms = {}
            ms[name] = slow_val
            save_config_value("motor_slow", ms)
            
            # Update motor_max config
            mx = get_config_value("motor_max", {})
            if not isinstance(mx, dict):
                mx = {}
            mx[name] = max_val
            save_config_value("motor_max", mx)
            
            # Reinitialize motor controller for power changes (so they take effect immediately)
            try:
                import control.motor_controller as mc
                mc.motor_controller.reload_config_and_reinit()
                print(f"Motor controller reinitialized for axis power settings: {name}")
            except Exception as e:
                print(f"Error reinitializing motor controller: {e}")
            
            updated = True
        except Exception as e:
            return (cfg, f"/testing?error=Failed+to+save+axis+config:+{str(e)}")
            
    elif action == "save_function_config":
        # Save function motor configuration (min power and travel safety)
        name = fields.get("name")
        
        try:
            min_power = int(fields.get("min_power", 40))
            travel_safety = bool(fields.get("travel_safety", False))
            forward_limit = float(fields.get("forward_limit", 0.0))
            reverse_limit = float(fields.get("reverse_limit", 0.0))
            
            # Clamp values to valid range
            min_power = min(65, max(1, min_power))
            forward_limit = max(0.0, min(60.0, forward_limit))
            reverse_limit = max(0.0, min(60.0, reverse_limit))
            
            # Update motor_min config
            mm = get_config_value("motor_min", {})
            if not isinstance(mm, dict):
                mm = {}
            mm[name] = min_power * 1000
            save_config_value("motor_min", mm)
            
            # Update travel safety configs
            safety_enabled = get_config_value("motor_travel_safety_enabled", {})
            if not isinstance(safety_enabled, dict):
                safety_enabled = {}
            safety_enabled[name] = travel_safety
            save_config_value("motor_travel_safety_enabled", safety_enabled)
            
            forward_limits = get_config_value("motor_travel_safety_forward", {})
            if not isinstance(forward_limits, dict):
                forward_limits = {}
            forward_limits[name] = forward_limit
            save_config_value("motor_travel_safety_forward", forward_limits)
            
            reverse_limits = get_config_value("motor_travel_safety_reverse", {})
            if not isinstance(reverse_limits, dict):
                reverse_limits = {}
            reverse_limits[name] = reverse_limit
            save_config_value("motor_travel_safety_reverse", reverse_limits)
            
            # Reinitialize motor controller for power changes (so they take effect immediately)
            # Travel safety changes still require restart since they're in control processor
            try:
                import control.motor_controller as mc
                mc.motor_controller.reload_config_and_reinit()
                print(f"Motor controller reinitialized for function power setting: {name} = {min_power}")
            except Exception as e:
                print(f"Error reinitializing motor controller: {e}")
            
            updated = True
        except Exception as e:
            return (cfg, f"/testing?error=Failed+to+save+function+config:+{str(e)}")
        
    # Reload config to reflect changes
    if updated:
        # Use in-place reinitialization to pick up new config
        try:
            import control.motor_controller as mc_mod
            mc_mod.motor_controller.reload_config_and_reinit()
        except Exception as e:
            print(f"Error reloading motor controller config: {e}")
            
    return (None, "/testing")


# Make unified handler accessible as module functions
handle_get = testing_handler.handle_get
handle_post = testing_handler.handle_post
