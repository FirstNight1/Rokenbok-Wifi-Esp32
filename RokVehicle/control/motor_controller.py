# control/motor_controller.py

import time
from machine import Pin, PWM
from RokCommon.variables.vars_store import get_config_value, save_config_value
from RokCommon.variables.vehicle_types import VEHICLE_TYPES
import gc

try:
    from control.function_controller import FunctionController
except Exception:
    FunctionController = None

PWM_FREQ = 1000  # Reduced from 2000Hz - some motor drivers work better with lower frequency
MAX_DUTY = 65535
WATCHDOG_TIMEOUT_MS = 2000

# Pin map controls which pins are used by motors, so motor 1 using pins 1 and 2, etc.
MOTOR_PIN_MAP = {
    1: (1, 2),  # D0 and D1
    2: (3, 4),  # D2 and D3
    3: (5, 6),  # D4 and D5
    4: (43, 44),  # D6 and D7
    5: (7, 8),  # D8 and D9
}


class Motor:
    def deinit(self):
        # Deinitialize PWM objects to free hardware channels
        try:
            self.pwm_a.deinit()
        except Exception:
            pass
        try:
            self.pwm_b.deinit()
        except Exception:
            pass

    def __init__(self, name, motor_num, reversed=False, motor_controller_ref=None):
        self.name = name
        self.motor_num = motor_num
        self.reversed = reversed

        if motor_num not in MOTOR_PIN_MAP:
            # Find next available motor number instead of defaulting to 1
            if motor_controller_ref and hasattr(
                motor_controller_ref, "_find_next_available_motor_num"
            ):
                # Get current motor assignments to find next available
                motor_numbers = get_config_value("motor_numbers", {})
                motor_num = motor_controller_ref._find_next_available_motor_num(
                    motor_numbers
                )
                self.motor_num = motor_num  # Update the stored motor_num
                print(
                    f"Warning: Motor {name} had invalid motor_num, assigned motor {motor_num}"
                )
            else:
                print(
                    f"Warning: Motor {name} has invalid motor_num {motor_num}, using motor 1"
                )
                motor_num = 1
                self.motor_num = 1

        a, b = MOTOR_PIN_MAP[motor_num]
        try:
            self.pwm_a = PWM(Pin(a), freq=PWM_FREQ, duty_u16=0)
            self.pwm_b = PWM(Pin(b), freq=PWM_FREQ, duty_u16=0)
        except Exception as e:
            print(f"ERROR: Failed to initialize PWM for motor {name} on pins {a},{b}: {e}")
            self.pwm_a = None
            self.pwm_b = None

        self.last_update_ms = time.ticks_ms()
        self.running = False
        # min_power is duty_u16 value (0..65535). Default populated by
        # MotorController after construction.
        self.min_power = None
        self.slow_power = None
        self.max_power = None
        
        # Travel safety configuration (read by control_processor)
        self.travel_safety_enabled = False
        self.travel_forward_limit = 0.0
        self.travel_reverse_limit = 0.0

    def stop(self):
        try:
            if self.pwm_a and self.pwm_b:
                self.pwm_a.duty_u16(0)
                self.pwm_b.duty_u16(0)
            self.running = False
        except Exception as e:
            print(f"Error stopping motor {self.name}: {e}")
            self.running = False

    def set_output_axis(self, direction, power, use_slow_mode=False):
        # Axis motor: power is 0..1, mapped to [min_power..max_power]
        try:
            if not self.pwm_a or not self.pwm_b:
                return  # PWM not available

            if power <= 0:
                duty = 0
            else:
                min_p = self.min_power if self.min_power is not None else 40000
                if use_slow_mode and self.slow_power is not None:
                    max_p = self.slow_power
                else:
                    max_p = self.max_power if self.max_power is not None else MAX_DUTY
                
                p = max(0.0, min(1.0, float(power)))
                duty = int(min_p + p * (max_p - min_p))

            forward = direction == "fwd"
            if self.reversed:
                forward = not forward

            if forward:
                self.pwm_a.duty_u16(duty)
                self.pwm_b.duty_u16(0)
            else:
                self.pwm_a.duty_u16(0)
                self.pwm_b.duty_u16(duty)
            
            self.running = duty > 0
            self.last_update_ms = time.ticks_ms()
            
        except Exception as e:
            print(f"Error setting motor {self.name} output: {e}")
            # Emergency stop
            try:
                if self.pwm_a:
                    self.pwm_a.duty_u16(0)
                if self.pwm_b:
                    self.pwm_b.duty_u16(0)
            except:
                pass
            self.running = False

    def set_output_function(self, direction, on):
        # Function motor: on=True sets min_power (with fallback), off sets 0
        try:
            if not self.pwm_a or not self.pwm_b:
                return  # PWM not available

            min_p = self.min_power if self.min_power is not None else 40000
            duty = int(min_p if on else 0)
            forward = direction == "fwd"
            if self.reversed:
                forward = not forward
            if forward:
                self.pwm_a.duty_u16(duty)
                self.pwm_b.duty_u16(0)
            else:
                self.pwm_a.duty_u16(0)
                self.pwm_b.duty_u16(duty)
            self.running = True if on else False
            self.last_update_ms = time.ticks_ms()
        except Exception as e:
            print(f"Error setting motor {self.name} output (function): {e}")
            # Try to safely stop the motor
            try:
                if self.pwm_a:
                    self.pwm_a.duty_u16(0)
                if self.pwm_b:
                    self.pwm_b.duty_u16(0)
            except:
                pass
            self.running = False
    


    def set_output(self, direction, value, mode="axis", use_slow_mode=False):
        # Dispatcher: mode is "axis" or "function"
        if mode == "function":
            self.set_output_function(direction, bool(value))
        else:
            self.set_output_axis(direction, value, use_slow_mode)


class MotorController:
    def deinit_all(self):
        # Deinitialize all motors' PWM objects
        for m in list(getattr(self, "axis_motors", {}).values()):
            try:
                m.deinit()
            except Exception:
                pass
        for m in list(getattr(self, "motor_functions", {}).values()):
            try:
                m.deinit()
            except Exception:
                pass

    def get_motor_assignments(self):
        """Return a dict mapping motor name to motor number and pin assignment."""
        assignments = {}
        for name, m in self.axis_motors.items():
            assignments[name] = {
                "motor_num": m.motor_num,
                "pins": MOTOR_PIN_MAP.get(m.motor_num, (None, None)),
            }
        for name, m in self.motor_functions.items():
            assignments[name] = {
                "motor_num": m.motor_num,
                "pins": MOTOR_PIN_MAP.get(m.motor_num, (None, None)),
            }
        return assignments

    def set_motor_assignments(self, assignments):
        """Update motor name to motor number mapping. assignments: {name: motor_num}. Validates uniqueness and range."""
        # Validate uniqueness
        nums = list(assignments.values())
        if len(nums) != len(set(nums)):
            raise ValueError("Motor numbers must be unique.")
        # Validate all numbers are in MOTOR_PIN_MAP
        for n in nums:
            if n not in MOTOR_PIN_MAP:
                raise ValueError(f"Invalid motor number: {n}")
        # Update config
        # MicroPython: ensure assignments is a plain dict, not a subclass
        motor_numbers = dict((str(k), int(v)) for k, v in assignments.items())
        save_config_value("motor_numbers", motor_numbers)
        
        # Reinitialize motor controller immediately to apply new pin assignments
        try:
            # Use in-place reinitialization instead of creating new instance
            self.reload_config_and_reinit()
            print(f"Motor assignments updated and applied immediately: {motor_numbers}")
        except Exception as e:
            print(f"Error applying motor assignments: {e}")
            print("Motor assignments saved but may require restart")
        
        return True

    def _find_next_available_motor_num(self, motor_numbers):
        """Find the next available motor number not in the motor_numbers dict"""
        used_numbers = set(motor_numbers.values())
        for num in range(1, 6):  # Motors 1-5 available
            if num not in used_numbers:
                return num
        return 1  # Fallback if all are somehow used

    def stop_motor(self, name):
        """Stop a motor by name, whether axis or function motor."""
        if name in self.axis_motors:
            self.axis_motors[name].stop()
        elif name in self.motor_functions:
            self.motor_functions[name].stop()

    def __init__(self):
        vtype = get_config_value("vehicleType")
        vinfo = next((v for v in VEHICLE_TYPES if v["typeName"] == vtype), None)
        if not vinfo:
            print(
                f"Warning: Vehicle type '{vtype}' not found, using default loader type"
            )
            vinfo = next((v for v in VEHICLE_TYPES if v["typeName"] == "loader"), None)
            if not vinfo:
                print("Error: Default loader vehicle type not found in VEHICLE_TYPES")
                # Create minimal fallback configuration
                vinfo = {"axis_motors": [], "motor_functions": []}

        # Get custom motor number mapping if present
        motor_numbers = get_config_value("motor_numbers", {})

        # Axis motors (continuous, axis-assignable)
        self.axis_motors = {}
        motor_reversed_cfg = get_config_value("motor_reversed", {})

        # Assign motor numbers to axis motors, preserving existing mappings
        for name in vinfo.get("axis_motors", []):
            if name in motor_numbers:
                motor_num = int(motor_numbers[name])
            else:
                motor_num = self._find_next_available_motor_num(motor_numbers)
                motor_numbers[name] = (
                    motor_num  # Add to motor_numbers to avoid conflicts
                )
            reversed_val = bool(motor_reversed_cfg.get(name, False))
            self.axis_motors[name] = Motor(
                name, motor_num, reversed=reversed_val, motor_controller_ref=self
            )

        # Motor functions (button-assignable, fwd/rev, on/off)
        self.motor_functions = {}
        # Assign motor numbers preserving existing mappings
        for name in vinfo.get("motor_functions", []):
            if name in motor_numbers:
                motor_num = int(motor_numbers[name])
            else:
                motor_num = self._find_next_available_motor_num(motor_numbers)
                motor_numbers[name] = (
                    motor_num  # Add to motor_numbers to avoid conflicts
                )
            reversed_val = bool(motor_reversed_cfg.get(name, False))
            self.motor_functions[name] = Motor(
                name, motor_num, reversed=reversed_val, motor_controller_ref=self
            )

        # Logic functions (on/off pins, e.g., lights, siren)
        self.functions = {}
        if FunctionController and vinfo.get("functions"):
            pin_map = {fname: 10 + idx for idx, fname in enumerate(vinfo["functions"])}
            self.function_controller = FunctionController(pin_map)
            self.functions = {fname: False for fname in vinfo["functions"]}
        else:
            self.function_controller = None

        # Load per-motor power values from config
        motor_min_cfg = get_config_value("motor_min", {})
        motor_slow_cfg = get_config_value("motor_slow", {})
        motor_max_cfg = get_config_value("motor_max", {})
        
        # Load travel safety configs
        motor_travel_safety_enabled_cfg = get_config_value("motor_travel_safety_enabled", {})
        motor_travel_safety_forward_cfg = get_config_value("motor_travel_safety_forward", {})
        motor_travel_safety_reverse_cfg = get_config_value("motor_travel_safety_reverse", {})
        
        # Configure axis motors
        for name, m in self.axis_motors.items():
            try:
                m.min_power = int(motor_min_cfg.get(name, 40000))
                m.slow_power = int(motor_slow_cfg.get(name, 50000))
                m.max_power = int(motor_max_cfg.get(name, 65535))
            except Exception:
                m.min_power = 40000
                m.slow_power = 50000
                m.max_power = 65535
        
        # Configure function motors        
        for name, m in self.motor_functions.items():
            try:
                m.min_power = int(motor_min_cfg.get(name, 40000))
                # Travel safety configuration for function motors
                m.travel_safety_enabled = bool(motor_travel_safety_enabled_cfg.get(name, False))
                m.travel_forward_limit = float(motor_travel_safety_forward_cfg.get(name, 0.0))
                m.travel_reverse_limit = float(motor_travel_safety_reverse_cfg.get(name, 0.0))
            except Exception:
                m.min_power = 40000
                m.travel_safety_enabled = False
                m.travel_forward_limit = 0.0
                m.travel_reverse_limit = 0.0

        # Save updated motor assignments back to config if any were added
        if motor_numbers != get_config_value("motor_numbers", {}):
            save_config_value("motor_numbers", motor_numbers)

    def reload_config_and_reinit(self):
        """Reload configuration and reinitialize all motors in-place"""
        print("Reloading motor controller configuration...")
        
        # Deinitialize all current motors
        self.deinit_all()
        
        # Clear current motor collections
        self.axis_motors = {}
        self.motor_functions = {}
        self.functions = {}
        
        # Re-run the initialization logic
        vtype = get_config_value("vehicleType")
        vinfo = next((v for v in VEHICLE_TYPES if v["typeName"] == vtype), None)
        if not vinfo:
            print(
                f"Warning: Vehicle type '{vtype}' not found, using default loader type"
            )
            vinfo = next((v for v in VEHICLE_TYPES if v["typeName"] == "loader"), None)
            if not vinfo:
                print("Error: Default loader vehicle type not found in VEHICLE_TYPES")
                vinfo = {"axis_motors": [], "motor_functions": []}

        # Get current motor assignments and reversed settings
        motor_numbers = get_config_value("motor_numbers", {})
        motor_reversed_cfg = get_config_value("motor_reversed", {})

        # Recreate axis motors
        for name in vinfo.get("axis_motors", []):
            if name in motor_numbers:
                motor_num = int(motor_numbers[name])
            else:
                motor_num = self._find_next_available_motor_num(motor_numbers)
                motor_numbers[name] = motor_num
            reversed_val = bool(motor_reversed_cfg.get(name, False))
            self.axis_motors[name] = Motor(
                name, motor_num, reversed=reversed_val, motor_controller_ref=self
            )

        # Recreate motor functions
        for name in vinfo.get("motor_functions", []):
            if name in motor_numbers:
                motor_num = int(motor_numbers[name])
            else:
                motor_num = self._find_next_available_motor_num(motor_numbers)
                motor_numbers[name] = motor_num
            reversed_val = bool(motor_reversed_cfg.get(name, False))
            self.motor_functions[name] = Motor(
                name, motor_num, reversed=reversed_val, motor_controller_ref=self
            )

        # Recreate function controller
        if FunctionController and vinfo.get("functions"):
            pin_map = {fname: 10 + idx for idx, fname in enumerate(vinfo["functions"])}
            self.function_controller = FunctionController(pin_map)
            self.functions = {fname: False for fname in vinfo["functions"]}
        else:
            self.function_controller = None

        # Reload and apply motor power configuration
        motor_min_cfg = get_config_value("motor_min", {})
        motor_slow_cfg = get_config_value("motor_slow", {})
        motor_max_cfg = get_config_value("motor_max", {})
        
        # Reload travel safety configs
        motor_travel_safety_enabled_cfg = get_config_value("motor_travel_safety_enabled", {})
        motor_travel_safety_forward_cfg = get_config_value("motor_travel_safety_forward", {})
        motor_travel_safety_reverse_cfg = get_config_value("motor_travel_safety_reverse", {})
        
        # Apply configuration to axis motors
        for name, m in self.axis_motors.items():
            try:
                m.min_power = int(motor_min_cfg.get(name, 40000))
                m.slow_power = int(motor_slow_cfg.get(name, 50000))
                m.max_power = int(motor_max_cfg.get(name, 65535))
            except Exception:
                m.min_power = 40000
                m.slow_power = 50000
                m.max_power = 65535
        
        # Apply configuration to function motors        
        for name, m in self.motor_functions.items():
            try:
                m.min_power = int(motor_min_cfg.get(name, 40000))
                m.travel_safety_enabled = bool(motor_travel_safety_enabled_cfg.get(name, False))
                m.travel_forward_limit = float(motor_travel_safety_forward_cfg.get(name, 0.0))
                m.travel_reverse_limit = float(motor_travel_safety_reverse_cfg.get(name, 0.0))
            except Exception:
                m.min_power = 40000
                m.travel_safety_enabled = False
                m.travel_forward_limit = 0.0
                m.travel_reverse_limit = 0.0

        # Save updated motor assignments if any were added
        if motor_numbers != get_config_value("motor_numbers", {}):
            save_config_value("motor_numbers", motor_numbers)
        
        print("Motor controller reloaded and reinitialized")

        # Load motor safety timeout from config (default 400ms for good responsiveness)
        self.timeout_ms = get_config_value("motor_safety_timeout_ms", 400)

    def update_safety_timeout(self):
        """Update the safety timeout from config - call after config changes"""
        new_timeout = get_config_value("motor_safety_timeout_ms", 400)
        if new_timeout != self.timeout_ms:
            self.timeout_ms = new_timeout
            print(f"Motor safety timeout updated to {self.timeout_ms}ms")

    # --------------------
    # Public API
    # --------------------




        

    

    
    def run_motor(self, name, direction, power_percentage, use_slow_mode=False):
        """
        Unified motor control method called by control_processor
        Handles both axis and function motors with power percentage (0-100)
        """
        
        if name in self.axis_motors:
            # Axis motor: handle slow mode, tracking adjustment, and power mapping
            m = self.axis_motors[name]
            
            # Apply drive tracking adjustment for left and right motors
            adjusted_percentage = power_percentage
            if name in ["left", "right"] and power_percentage > 0:
                tracking_adjustment = get_config_value("drive_tracking_adjustment", 0.0)
                if tracking_adjustment != 0.0:
                    adjustment_factor = abs(tracking_adjustment) / 100.0
                    # If tracking_adjustment is positive, vehicle tracks right, so reduce left motor
                    # If tracking_adjustment is negative, vehicle tracks left, so reduce right motor
                    if (tracking_adjustment > 0 and name == "left") or (tracking_adjustment < 0 and name == "right"):
                        adjusted_percentage = power_percentage * (1.0 - adjustment_factor)
            
            # Convert percentage to 0-1 normalized value
            normalized_power = adjusted_percentage / 100.0
            
            # Set output with slow mode flag
            m.set_output(direction, normalized_power, mode="axis", use_slow_mode=use_slow_mode)
            
        elif name in self.motor_functions:
            # Function motor: simple on/off based on power percentage
            # Travel safety is handled by control_processor before this method is called
            m = self.motor_functions[name]
            is_on = power_percentage > 0
            
            # Set output using function mode (uses min_power as the "set power")
            m.set_output(direction, is_on, mode="function")
        else:
            print(f"Unknown motor: {name}")
    






    def emergency_stop_all(self):
        """Emergency stop all motors immediately"""
        print("EMERGENCY STOP: Stopping all motors")
        try:
            for m in list(self.axis_motors.values()) + list(self.motor_functions.values()):
                try:
                    if hasattr(m, 'pwm_a') and m.pwm_a:
                        m.pwm_a.duty_u16(0)
                    if hasattr(m, 'pwm_b') and m.pwm_b:
                        m.pwm_b.duty_u16(0)
                    m.running = False
                except Exception as e:
                    print(f"Error emergency stopping motor {getattr(m, 'name', 'unknown')}: {e}")
            
            if self.function_controller:
                try:
                    for fname in self.functions:
                        self.function_controller.set_function(fname, False)
                except Exception as e:
                    print(f"Error stopping function controller: {e}")
        except Exception as e:
            print(f"Error in emergency_stop_all(): {e}")

    def stop_all(self):
        try:
            for m in list(self.axis_motors.values()) + list(self.motor_functions.values()):
                try:
                    m.stop()
                except Exception as e:
                    print(f"Error stopping motor {getattr(m, 'name', 'unknown')}: {e}")
            
            if self.function_controller:
                try:
                    for fname in self.functions:
                        self.function_controller.set_function(fname, False)
                except Exception as e:
                    print(f"Error stopping function controller: {e}")
        except Exception as e:
            print(f"Error in stop_all(): {e}")

    # --------------------
    # Watchdog (No longer used - control_processor handles safety)
    # --------------------
                
    def is_busy(self):
        """Check if vehicle is currently busy (considering override settings)"""
        try:
            # Import here to avoid circular imports
            from web.web_server import get_effective_busy_status
            return get_effective_busy_status()
        except Exception:
            # Fallback to WebSocket client check if override function unavailable
            try:
                from web.web_server import WS_CLIENT
                return bool(WS_CLIENT)
            except Exception:
                return False


# Global motor controller instance
_motor_controller_instance = None

def get_motor_controller():
    """Get the global motor controller instance if available"""
    global _motor_controller_instance
    return _motor_controller_instance

def set_motor_controller(instance):
    """Set the global motor controller instance"""
    global _motor_controller_instance
    _motor_controller_instance = instance


motor_controller = MotorController()
set_motor_controller(motor_controller)
