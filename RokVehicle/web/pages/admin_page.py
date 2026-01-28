from RokCommon.web.request_response import Response
from RokCommon.variables.vars_store import get_config_value, save_config_value
from RokCommon.variables.vehicle_types import VEHICLE_TYPES
from RokCommon.web.pages.home_page import load_and_process_header


def _valid_vehicle_types():
    """Return list of valid vehicle type names"""
    return {t["typeName"] for t in VEHICLE_TYPES}


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
    # Get current vehicle type and motor configuration
    vtype = get_config_value("vehicleType")
    vinfo = next((v for v in VEHICLE_TYPES if v["typeName"] == vtype), None)
    if not vinfo:
        return ""
    
    function_motors = vinfo.get("motor_functions", [])
    if not function_motors:
        return "<p>No function motors configured for this vehicle type.</p>"
    
    # Get current config values
    motor_min_cfg = get_config_value("motor_min", {})
    motor_travel_safety_enabled_cfg = get_config_value("motor_travel_safety_enabled", {})
    motor_travel_safety_forward_cfg = get_config_value("motor_travel_safety_forward", {})
    motor_travel_safety_reverse_cfg = get_config_value("motor_travel_safety_reverse", {})
    
    html = []
    for motor_name in function_motors:
        min_val = motor_min_cfg.get(motor_name, 40000) // 1000  # Convert to 1-65 range
        safety_enabled = motor_travel_safety_enabled_cfg.get(motor_name, False)
        forward_limit = motor_travel_safety_forward_cfg.get(motor_name, 0.0)
        reverse_limit = motor_travel_safety_reverse_cfg.get(motor_name, 0.0)
        
        html.append(f"""
        <div style="margin-bottom: 15px; padding: 10px; border: 1px solid #ddd; border-radius: 3px;">
            <h5 style="margin: 0 0 10px 0; color: #444;">{str(motor_name)[0].upper() + str(motor_name)[1:] if len(str(motor_name)) > 0 else str(motor_name)} Motor</h5>
            <div style="display: flex; gap: 15px; flex-wrap: wrap; align-items: center; margin-bottom: 10px;">
                <div>
                    <label>Min Power (1-65):</label><br>
                    <input type="number" name="{motor_name}_min" value="{min_val}" min="1" max="65" style="width: 60px;">
                </div>
            </div>
            <div>
                <label>
                    <input type="checkbox" name="{motor_name}_travel_safety" {"checked" if safety_enabled else ""}>
                    Enable travel safety limits
                </label><br>
                <small style="color: #888; font-style: italic;">Note: Travel safety changes require restart to take effect</small><br>
                <div style="display: flex; gap: 15px; margin-top: 5px;">
                    <div>
                        <label>Forward Limit (seconds):</label><br>
                        <input type="number" name="{motor_name}_forward_limit" value="{forward_limit}" min="0" max="60" step="0.1" style="width: 80px;">
                    </div>
                    <div>
                        <label>Reverse Limit (seconds):</label><br>
                        <input type="number" name="{motor_name}_reverse_limit" value="{reverse_limit}" min="0" max="60" step="0.1" style="width: 80px;">
                    </div>
                </div>
                <small style="color: #666;">Prevents motor operation beyond these time limits to protect clutches</small>
            </div>
        </div>""")
    
    return "".join(html)


def _save_motor_configs(fields):
    """Save motor configuration from form fields"""
    # Get current vehicle type and motor configuration
    vtype = get_config_value("vehicleType")
    vinfo = next((v for v in VEHICLE_TYPES if v["typeName"] == vtype), None)
    if not vinfo:
        return
    
    # Load current configs
    motor_min_cfg = get_config_value("motor_min", {})
    motor_slow_cfg = get_config_value("motor_slow", {})
    motor_max_cfg = get_config_value("motor_max", {})
    motor_travel_safety_enabled_cfg = get_config_value("motor_travel_safety_enabled", {})
    motor_travel_safety_forward_cfg = get_config_value("motor_travel_safety_forward", {})
    motor_travel_safety_reverse_cfg = get_config_value("motor_travel_safety_reverse", {})
    
    # Process axis motors (drive motors)
    axis_motors = vinfo.get("axis_motors", [])
    for motor_name in axis_motors:
        try:
            # Parse min, slow, max values (1-65 range, convert to actual values)
            min_val = int(fields.get(f"{motor_name}_min", 40)) * 1000
            slow_val = int(fields.get(f"{motor_name}_slow", 50)) * 1000
            max_val = int(fields.get(f"{motor_name}_max", 65))
            
            # Handle max power special case (65 -> 65535)
            if max_val >= 65:
                max_val = 65535
            else:
                max_val *= 1000
            
            # Validate ranges
            min_val = max(1000, min(65000, min_val))
            slow_val = max(min_val, min(65000, slow_val))
            max_val = max(slow_val, min(65535, max_val))
            
            motor_min_cfg[motor_name] = min_val
            motor_slow_cfg[motor_name] = slow_val
            motor_max_cfg[motor_name] = max_val
            
        except (ValueError, TypeError) as e:
            print(f"Invalid motor config for {motor_name}: {e}")
    
    # Process function motors  
    function_motors = vinfo.get("motor_functions", [])
    for motor_name in function_motors:
        try:
            # Parse min value
            min_val = int(fields.get(f"{motor_name}_min", 40)) * 1000
            min_val = max(1000, min(65000, min_val))
            motor_min_cfg[motor_name] = min_val
            
            # Parse travel safety settings
            safety_enabled = f"{motor_name}_travel_safety" in fields
            motor_travel_safety_enabled_cfg[motor_name] = safety_enabled
            
            if safety_enabled:
                forward_limit = float(fields.get(f"{motor_name}_forward_limit", 0.0))
                reverse_limit = float(fields.get(f"{motor_name}_reverse_limit", 0.0))
                
                # Validate ranges (0-60 seconds, round to 1 decimal place)
                forward_limit = max(0.0, min(60.0, round(forward_limit, 1)))
                reverse_limit = max(0.0, min(60.0, round(reverse_limit, 1)))
                
                motor_travel_safety_forward_cfg[motor_name] = forward_limit
                motor_travel_safety_reverse_cfg[motor_name] = reverse_limit
            
        except (ValueError, TypeError) as e:
            print(f"Invalid function motor config for {motor_name}: {e}")
    
    # Save all configs
    save_config_value("motor_min", motor_min_cfg)
    save_config_value("motor_slow", motor_slow_cfg)  
    save_config_value("motor_max", motor_max_cfg)
    save_config_value("motor_travel_safety_enabled", motor_travel_safety_enabled_cfg)
    save_config_value("motor_travel_safety_forward", motor_travel_safety_forward_cfg)
    save_config_value("motor_travel_safety_reverse", motor_travel_safety_reverse_cfg)


# Helper functions


def build_admin_page(cfg):
    try:
        # Load header navigation using shared function
        header_nav = load_and_process_header(cfg.get("vehicleName", ""))
        if not header_nav:
            header_nav = "<div>Header not found</div>"

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

        # Build vehicle type options
        type_options = "".join(
            [
                f"<option value='{t['typeName']}' {'selected' if cfg.get('vehicleType') == t['typeName'] else ''}>{t['typeFriendlyName']}</option>"
                for t in VEHICLE_TYPES
            ]
        )

        # Build vehicle type mapping for JavaScript
        vehicle_type_map = {}
        for t in VEHICLE_TYPES:
            if t["typeName"] == "fpv":
                vehicle_type_map[t["typeName"]] = "RokVision"
            else:
                vehicle_type_map[t["typeName"]] = t["tagName"]

        # Convert to JavaScript object properties (comma-separated key-value pairs)
        vehicle_type_js = "{" + ", ".join(
            [
                f'"{type_name}": "{tag_prefix}"'
                for type_name, tag_prefix in vehicle_type_map.items()
            ]
        ) + "}"

        # LED pin options with current values
        led_enabled = cfg.get("ledEnabled", True)
        current_led_pin = cfg.get("ledPin", 9)
        busy_led_enabled = cfg.get("busyLedEnabled", False)
        current_busy_led_pin = cfg.get("busyLedPin", -1)

        # Get current motor pin assignments to mark them as unavailable
        motor_numbers = get_config_value("motor_numbers", {})
        used_pins = set()
        for motor_name, motor_num in motor_numbers.items():
            if motor_num in [1, 2, 3, 4, 5]:
                pin_map = {1: (1, 2), 2: (3, 4), 3: (5, 6), 4: (43, 44), 5: (7, 8)}
                if motor_num in pin_map:
                    used_pins.update(pin_map[motor_num])

        # Build LED pin options with smart conflict detection
        # Import pin mapping for proper pin names
        from RokCommon.control.network_led import NETWORK_LED_PINS
        
        available_pins = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 21, 41, 42, 43, 44]
        
        # Check for shared LED mode (same pin for both LEDs)
        shared_led_mode = led_enabled and busy_led_enabled and current_led_pin == current_busy_led_pin and current_led_pin != -1
        shared_led_note = ""
        if shared_led_mode:
            pin_name = NETWORK_LED_PINS.get(current_led_pin, f"GPIO{current_led_pin}")
            shared_led_note = f"""
            <div style="border: 1px solid #ff9800; padding: 10px; margin: 10px 0; border-radius: 5px; background: #fff3e0;">
                <strong>Shared LED Mode Active (Pin {pin_name}):</strong><br>
                Network status will display for startup and connection, then after 30 seconds 
                the LED will switch to busy status indication for vehicle operation.
            </div>
            """
        
        # Network LED pin options (with disabled option)
        led_pin_options = ["<option value='-1' {}>Disabled</option>".format("selected" if current_led_pin == -1 else "")]
        
        # Busy LED pin options (with disabled option)
        busy_led_pin_options = ["<option value='-1' {}>Disabled</option>".format("selected" if current_busy_led_pin == -1 else "")]
        
        for pin in available_pins:
            is_used_by_motor = pin in used_pins
            is_current_led = pin == current_led_pin
            is_current_busy = pin == current_busy_led_pin
            
            # In shared mode, don't show conflict for the shared pin
            pin_conflicts = False
            if not shared_led_mode:  # Only check conflicts if not in shared mode
                if is_current_led and busy_led_enabled and pin == current_busy_led_pin:
                    pin_conflicts = True  # Same pin used by both LEDs
                elif is_current_busy and led_enabled and pin == current_led_pin:
                    pin_conflicts = True  # Same pin used by both LEDs
            
            # Only show pins as "used" if they're actually conflicting with enabled features
            show_as_used = (is_used_by_motor or pin_conflicts) and not (is_current_led or is_current_busy)
            
            # Style for used pins
            style_attr = 'style="color: #ccc; background: #f5f5f5;"' if show_as_used else ''
            
            # Get pin name from mapping, fallback to GPIO number
            pin_name = NETWORK_LED_PINS.get(pin, f"GPIO{pin}")
            
            # Network LED pin options
            selected_led = "selected" if is_current_led else ""
            led_pin_options.append(
                f'<option value="{pin}" {selected_led} {style_attr}>{pin_name}</option>'
            )
            
            # Busy LED pin options  
            selected_busy = "selected" if is_current_busy else ""
            busy_led_pin_options.append(
                f'<option value="{pin}" {selected_busy} {style_attr}>{pin_name}</option>'
            )

        led_pin_options_html = "\n                    ".join(led_pin_options)
        busy_led_pin_options_html = "\n                    ".join(busy_led_pin_options)

        # Load and build the full page
        html = _load_template("web/pages/assets/admin_page.html")
        if html is None:
            return "<html><body><h1>Admin page template not found</h1></body></html>"

        # Get values for display
        vehicle_tag = cfg.get("vehicleTag", "")
        vehicle_name = cfg.get("vehicleName", "")
        
        # Template replacements with safety checks for None values
        html = html.replace("{{ header_nav }}", (header_nav or "").strip().replace("\n", ""))
        html = html.replace("{{ type_option }}", (type_options or "").strip())
        html = html.replace("{{ vehicle_tag }}", (vehicle_tag or "").strip())
        html = html.replace("{{ vehicle_name }}", (vehicle_name or "").strip())
        html = html.replace("{{ vehicle_type_map }}", (vehicle_type_js or "").strip())
        html = html.replace("{{vehicle_type_map}}", (vehicle_type_js or "").strip())  # Support both formats
        html = html.replace("{{ led_status }}", "")  # Remove LED status display
        html = html.replace("{{ led_enabled_checked }}", "checked" if led_enabled else "")
        html = html.replace("{{ led_pin_options }}", (led_pin_options_html or "").strip())
        html = html.replace("{{ busy_led_enabled_checked }}", "checked" if busy_led_enabled else "")
        html = html.replace("{{ busy_led_pin_options }}", (busy_led_pin_options_html or "").strip())
        html = html.replace("{{ motor_safety_timeout }}", str(get_config_value("motor_safety_timeout_ms", 400)))
        html = html.replace("{{ keepalive_interval }}", str(get_config_value("keepalive_interval_ms", 200)))
        html = html.replace("{{ shared_led_note }}", shared_led_note)
        
        return html

    except Exception as e:
        print(f"Error building admin page: {e}")
        return f"<html><body><h1>Admin Page Error</h1><p>{str(e)}</p></body></html>"


class AdminHandler:
    """Admin page handler using unified Request/Response system"""

    def handle_get(self, request):
        """Handle GET requests for admin page"""
        try:
            # Check if this is a config request
            if request.query.get('config') == 'keepalive':
                import json
                config = {
                    "keepalive_interval_ms": get_config_value("keepalive_interval_ms", 200)
                }
                return Response.json(config)
            
            cfg = {
                "vehicleType": get_config_value("vehicleType"),
                "vehicleTag": get_config_value("vehicleTag"),
                "vehicleName": get_config_value("vehicleName"),
                "ledEnabled": get_config_value("ledEnabled", True),
                "ledPin": get_config_value("ledPin", 9),
                "busyLedEnabled": get_config_value("busyLedEnabled", False),
                "busyLedPin": get_config_value("busyLedPin", -1),
            }
            html = build_admin_page(cfg)
            return Response.html(html)
        except Exception as e:
            print(f"Admin page GET error: {e}")
            return Response.server_error(f"Error loading admin page: {str(e)}")

    def handle_post(self, request):
        """Handle POST requests for admin page"""
        try:
            # Parse form data
            fields = {}
            for pair in request.body.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    fields[k] = v.replace("+", " ")

            # Cancel → no changes saved
            if "cancel" in fields:
                return Response.redirect_to("/admin")

            # Validate vehicle type
            from RokCommon.variables.vehicle_types import VEHICLE_TYPES
            valid_types = {t["typeName"] for t in VEHICLE_TYPES}
            new_type = fields.get("vehicleType", get_config_value("vehicleType"))
            if new_type not in valid_types:
                print("⚠️ Invalid vehicleType received:", new_type)
                return Response.redirect_to("/admin")

            old_type = get_config_value("vehicleType")
            old_tag = get_config_value("vehicleTag", "")

            # Update tag if vehicle type changed
            new_tag = old_tag
            if old_type != new_type:
                # Find tagName for new type
                new_type_obj = next((t for t in VEHICLE_TYPES if t["typeName"] == new_type), None)
                if new_type_obj:
                    tag_prefix = new_type_obj["tagName"]
                    if old_tag.startswith(old_tag.split("-")[0] + "-"):
                        suffix = old_tag.split("-", 1)[1]
                        new_tag = tag_prefix + "-" + suffix
                    else:
                        new_tag = old_tag

            # If user manually changed vehicleTag, use their value
            tag_from_form = fields.get("vehicleTag")
            if tag_from_form is not None and tag_from_form != old_tag:
                new_tag = tag_from_form

            save_config_value("vehicleType", new_type)
            save_config_value("vehicleTag", new_tag)
            save_config_value(
                "vehicleName", fields.get("vehicleName", get_config_value("vehicleName"))
            )
            
            # Save LED configuration
            save_config_value("ledEnabled", 1 if "ledEnabled" in fields else 0)
            led_pin = int(fields.get("ledPin", get_config_value("ledPin", 9)))
            save_config_value("ledPin", led_pin)
            
            save_config_value("busyLedEnabled", 1 if "busyLedEnabled" in fields else 0)
            busy_led_pin = int(fields.get("busyLedPin", get_config_value("busyLedPin", -1)))
            save_config_value("busyLedPin", busy_led_pin)
            
            # Save motor safety timeout
            motor_safety_timeout = int(fields.get("motorSafetyTimeoutMs", get_config_value("motor_safety_timeout_ms", 400)))
            # Clamp to reasonable range (100ms to 5000ms)
            motor_safety_timeout = max(100, min(5000, motor_safety_timeout))
            save_config_value("motor_safety_timeout_ms", motor_safety_timeout)
            
            # Save keepalive interval
            keepalive_interval = int(fields.get("keepaliveIntervalMs", get_config_value("keepalive_interval_ms", 200)))
            # Clamp to reasonable range (50ms to 2000ms)
            keepalive_interval = max(50, min(2000, keepalive_interval))
            save_config_value("keepalive_interval_ms", keepalive_interval)
            
            # Save drive tracking adjustment
            try:
                drive_tracking = float(fields.get("driveTrackingAdjustment", get_config_value("drive_tracking_adjustment", 0.0)))
                # Clamp to reasonable range (-10% to +10%)
                drive_tracking = max(-10.0, min(10.0, drive_tracking))
                save_config_value("drive_tracking_adjustment", drive_tracking)
            except (ValueError, TypeError) as e:
                print(f"Invalid drive tracking value, using default: {e}")
                save_config_value("drive_tracking_adjustment", 0.0)
            
            # Save slow mode disable functions setting
            slow_mode_disable = "slowModeDisableFunctions" in fields
            save_config_value("slow_mode_disable_functions", slow_mode_disable)
            
            # Save motor configurations
            _save_motor_configs(fields)
            
            # Update motor controller timeout if available
            try:
                from control.motor_controller import get_motor_controller
                motor_controller = get_motor_controller()
                if motor_controller:
                    motor_controller.update_safety_timeout()
            except Exception as e:
                pass
            
            # Update LED configurations if changed
            try:
                from RokCommon.control.network_led import get_network_led, NETWORK_LED_PINS
                from control.vehicle_led import get_vehicle_led
                
                # Check for shared LED mode
                led_enabled = 1 if "ledEnabled" in fields else 0
                busy_enabled = 1 if "busyLedEnabled" in fields else 0
                shared_mode = (led_enabled and busy_enabled and 
                              led_pin != -1 and busy_led_pin != -1 and 
                              led_pin == busy_led_pin)
                
                # Always deinitialize and reconfigure network LED to ensure clean state
                network_led = get_network_led()
                if network_led:

                    
                    if led_enabled and led_pin != -1:
                        network_led.reinit_with_pin(led_pin, shared_mode)
                        # reinit_with_pin now starts fresh sequence automatically
                        if shared_mode:
                            print("Fresh network sequence started in shared mode")
                        else:
                            print("Fresh network sequence started in normal mode")
                    else:
                        # LED disabled - clean up and turn off
                        network_led.deinit()

                
                # Always deinitialize and reconfigure busy LED to ensure clean state
                vehicle_led = get_vehicle_led()
                if vehicle_led:
                    vehicle_led.deinit()  # Clean up old state
                    
                    if not shared_mode and busy_enabled and busy_led_pin != -1:
                        vehicle_led.reinit_busy_led(busy_led_pin)
                        vehicle_led.start_busy_monitoring()
                        pass
                    else:
                        # Busy LED disabled, no pin assigned, or in shared mode
                        if shared_mode:
                            pass
                        else:
                            pass
                        
                if shared_mode:
                    pin_name = NETWORK_LED_PINS.get(led_pin, f"GPIO{led_pin}")

                        
            except Exception as e:
                pass
            
            return Response.redirect_to("/admin")

        except Exception as e:
            print(f"Admin page POST error: {e}")
            return Response.server_error(f"Error processing admin form: {str(e)}")


# Create handler instance
admin_handler = AdminHandler()

def handle_post_legacy(body, cfg):
    """
    body = raw POST body (string)
    cfg  = dict from load_config() passed in by web_server
    """
    valid_types = _valid_vehicle_types()
    # Basic x-www-form-urlencoded decode
    fields = {}
    for pair in body.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            fields[k] = v.replace("+", " ")

    # Cancel → no changes saved
    if "cancel" in fields:
        return cfg, "/admin"

    # ---- HANDLE LED SETTINGS ----
    led_enabled = "ledEnabled" in fields
    led_pin = fields.get("ledPin", "9")

    # Validate LED pin
    try:
        led_pin_num = int(led_pin)
        if led_pin_num not in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 43, 44]:
            led_pin_num = 9  # Default fallback
    except:
        led_pin_num = 9

    # Update LED config
    cfg["ledEnabled"] = led_enabled
    cfg["ledPin"] = led_pin_num

    # Apply LED settings if changed
    from RokCommon.control.network_led import get_network_led_manager
    from control.vehicle_led import get_vehicle_led_manager

    # Update network LED manager
    network_led = get_network_led_manager()
    if network_led:
        # Check if pin changed
        old_pin = getattr(network_led, "led_pin_num", 9) 
        if old_pin != led_pin_num:
            # Reinitialize LED with new pin
            network_led.set_pin(led_pin_num)

        # Set override based on enabled state
        if not led_enabled:
            network_led.set_override(True, False)  # Force off
        else:
            network_led.set_override(False)  # Auto mode
            network_led.set_wifi_status()  # Update to current WiFi status

    # ---- VALIDATE VEHICLE TYPE ----
    new_type = fields.get("vehicleType", cfg.get("vehicleType"))
    if new_type not in valid_types:
        print("⚠️ Invalid vehicleType received:", new_type)
        return cfg, "/admin"

    old_type = cfg.get("vehicleType")
    old_tag = cfg.get("vehicleTag", "")
    # Find tagName for old and new type
    old_type_obj = next((t for t in VEHICLE_TYPES if t["typeName"] == old_type), None)
    new_type_obj = next((t for t in VEHICLE_TYPES if t["typeName"] == new_type), None)
    old_tag_prefix = old_type_obj["tagName"] if old_type_obj else old_type
    new_tag_prefix = new_type_obj["tagName"] if new_type_obj else new_type

    # If tag starts with old_tag_prefix + '-', update to new_tag_prefix + '-...'
    if old_tag.startswith(old_tag_prefix + "-"):
        suffix = old_tag[len(old_tag_prefix) + 1 :]
        new_tag = new_tag_prefix + "-" + suffix
    else:
        new_tag = old_tag

    # If user manually changed vehicleTag, use their value
    tag_from_form = fields.get("vehicleTag")
    if tag_from_form is not None and tag_from_form != old_tag:
        new_tag = tag_from_form

    save_config_value("vehicleType", new_type)
    save_config_value("vehicleTag", new_tag)
    save_config_value(
        "vehicleName", fields.get("vehicleName", get_config_value("vehicleName"))
    )
    
    # Save LED configuration
    save_config_value("ledEnabled", 1 if "ledEnabled" in fields else 0)
    led_pin = int(fields.get("ledPin", get_config_value("ledPin", 9)))
    save_config_value("ledPin", led_pin)
    
    save_config_value("busyLedEnabled", 1 if "busyLedEnabled" in fields else 0)
    busy_led_pin = int(fields.get("busyLedPin", get_config_value("busyLedPin", -1)))
    save_config_value("busyLedPin", busy_led_pin)
    
    # Save motor safety timeout
    motor_safety_timeout = int(fields.get("motorSafetyTimeoutMs", get_config_value("motor_safety_timeout_ms", 400)))
    # Clamp to reasonable range (100ms to 5000ms)
    motor_safety_timeout = max(100, min(5000, motor_safety_timeout))
    save_config_value("motor_safety_timeout_ms", motor_safety_timeout)
    
    # Save drive tracking adjustment
    try:
        drive_tracking = float(fields.get("driveTrackingAdjustment", get_config_value("drive_tracking_adjustment", 0.0)))
        # Clamp to reasonable range (-10% to +10%)
        drive_tracking = max(-10.0, min(10.0, drive_tracking))
        save_config_value("drive_tracking_adjustment", drive_tracking)
    except (ValueError, TypeError) as e:
        print(f"Invalid drive tracking value, using default: {e}")
        save_config_value("drive_tracking_adjustment", 0.0)
    
    # Update motor controller timeout if available
    try:
        from control.motor_controller import get_motor_controller
        motor_controller = get_motor_controller()
        if motor_controller:
            motor_controller.update_safety_timeout()
    except Exception as e:
        pass
    
    # Update LED configurations if changed
    try:
        from RokCommon.control.network_led import get_network_led
        from control.vehicle_led import get_vehicle_led
        
        # Update network LED
        network_led = get_network_led()
        if network_led:
            led_enabled = 1 if "ledEnabled" in fields else 0
            if led_enabled and led_pin != -1:
                network_led.reinit_with_pin(led_pin)
                network_led.set_wifi_status()  # Update pattern
            else:
                network_led.set_override(True, False)  # Turn off
        
        # Update busy LED
        vehicle_led = get_vehicle_led()
        if vehicle_led:
            busy_enabled = 1 if "busyLedEnabled" in fields else 0
            if busy_enabled and busy_led_pin != -1:
                vehicle_led.reinit_busy_led(busy_led_pin)
                vehicle_led.start_busy_monitoring()
            else:
                # Stop busy monitoring if disabled or no pin assigned
                vehicle_led.stop_busy_monitoring()
    except Exception as e:
        pass
    
    return None, "/admin"


# Create handler instance
admin_handler = AdminHandler()

# Make unified handler accessible as module functions
handle_get = admin_handler.handle_get
handle_post = admin_handler.handle_post

