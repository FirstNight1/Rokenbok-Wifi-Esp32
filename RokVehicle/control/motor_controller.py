# control/motor_controller.py

import time
from machine import Pin, PWM
from variables.vars_store import load_config, save_config
from variables.vehicle_types import VEHICLE_TYPES
try:
    from control.function_controller import FunctionController
except Exception:
    FunctionController = None

PWM_FREQ = 2000
MAX_DUTY = 65535

#Pin map controls which pins are used by motors, so motor 1 using pins 1 and 2, etc.
MOTOR_PIN_MAP = {
    1: (1, 2), #D0 and D1
    2: (3, 4), #D2 and D3
    3: (5, 6), #D4 and D5
    4: (43, 44), #D6 and D7
}

class Motor:

    def __init__(self, name, motor_num, reversed=False):
        self.name = name
        self.motor_num = motor_num
        self.reversed = reversed

        a, b = MOTOR_PIN_MAP[motor_num]
        self.pwm_a = PWM(Pin(a), freq=PWM_FREQ, duty_u16=0)
        self.pwm_b = PWM(Pin(b), freq=PWM_FREQ, duty_u16=0)

        self.last_update_ms = time.ticks_ms()
        self.running = False
        # min_power is duty_u16 value (0..65535). Default populated by
        # MotorController after construction.
        self.min_power = None

    def stop(self):
        self.pwm_a.duty_u16(0)
        self.pwm_b.duty_u16(0)
        self.running = False


    def set_output(self, direction, power):
        # power is expected 0..1. A value of 0 means fully off (duty=0).
        # For >0 power we map into [min_power .. MAX_DUTY].
        if power <= 0:
            duty = 0
        else:
            min_p = self.min_power if self.min_power is not None else 40000
            # clamp power
            p = max(0.0, min(1.0, float(power)))
            duty = int(min_p + p * (MAX_DUTY - min_p))
        forward = (direction == "fwd")

        if self.reversed:
            forward = not forward

        if forward:
            self.pwm_a.duty_u16(duty)
            self.pwm_b.duty_u16(0)
        else:
            self.pwm_a.duty_u16(0)
            self.pwm_b.duty_u16(duty)

        self.running = True
        self.last_update_ms = time.ticks_ms()



class MotorController:
    def update_reversed(self, name, reversed_value):
        """Update the reversed flag for a named motor and persist in config."""
        print(f"[DEBUG] update_reversed called: name={name}, reversed_value={reversed_value}")
        # Update in-memory value
        if name in self.axis_motors:
            self.axis_motors[name].reversed = bool(reversed_value)
            print(f"[DEBUG] axis_motors[{name}].reversed set to {self.axis_motors[name].reversed}")
        elif name in self.motor_functions:
            self.motor_functions[name].reversed = bool(reversed_value)
            print(f"[DEBUG] motor_functions[{name}].reversed set to {self.motor_functions[name].reversed}")
        else:
            print(f"[DEBUG] Motor {name} not found in axis_motors or motor_functions!")
            return False

        # Persist to config
        cfg = load_config()
        print(f"[DEBUG] Config before update: {cfg}")
        mr = cfg.get("motor_reversed")
        if not isinstance(mr, dict):
            mr = {}
        mr[name] = bool(reversed_value)
        cfg["motor_reversed"] = mr
        try:
            save_config(cfg)
            print(f"[DEBUG] Config after update: {cfg}")
        except Exception as e:
            print(f"[DEBUG] Exception saving config: {e}")
        return True
    def stop_motor(self, name):
        """Stop a motor by name, whether axis or function motor."""
        if name in self.axis_motors:
            self.axis_motors[name].stop()
        elif name in self.motor_functions:
            self.motor_functions[name].stop()
    def set_motor(self, name, direction, power):
        if name in self.axis_motors:
            self.axis_motors[name].set_output(direction, power)
        elif name in self.motor_functions:
            self.motor_functions[name].set_output(direction, power)
        else:
            print(f"  -> motor {name} not found!")
    def __init__(self):
        cfg = load_config()
        vtype = cfg.get("vehicleType")
        vinfo = next((v for v in VEHICLE_TYPES if v["typeName"] == vtype), None)
        if not vinfo:
            raise ValueError("Vehicle type not found")

        # Axis motors (continuous, axis-assignable)
        self.axis_motors = {}
        for idx, name in enumerate(vinfo.get("axis_motors", [])):
            # Assign motor numbers 1,2 for axis motors by default
            self.axis_motors[name] = Motor(name, idx+1)

        # Motor functions (button-assignable, fwd/rev, on/off)
        self.motor_functions = {}
        for idx, name in enumerate(vinfo.get("motor_functions", [])):
            # Assign motor numbers 3,4... for motor functions by default
            self.motor_functions[name] = Motor(name, idx+3)

        # Logic functions (on/off pins, e.g., lights, siren)
        self.functions = {}
        if FunctionController and vinfo.get("functions"):
            # Assign pins 10+ for logic functions (customize as needed)
            pin_map = {fname: 10+idx for idx, fname in enumerate(vinfo["functions"])}
            self.function_controller = FunctionController(pin_map)
            self.functions = {fname: False for fname in vinfo["functions"]}
        else:
            self.function_controller = None

        # Load per-motor min power values from config (if present)
        motor_min_cfg = cfg.get("motor_min", {})
        for name, m in self.axis_motors.items():
            try:
                m.min_power = int(motor_min_cfg.get(name, 40000))
            except Exception:
                m.min_power = 40000
        for name, m in self.motor_functions.items():
            try:
                m.min_power = int(motor_min_cfg.get(name, 40000))
            except Exception:
                m.min_power = 40000

        self.timeout_ms = 200

    # --------------------
    # Public API
    # --------------------

    def set_axis(self, name, value):
        # value: -1..1 (float), mapped to direction/power
        m = self.axis_motors.get(name)
        if not m:
            return
        direction = "fwd" if value >= 0 else "rev"
        power = abs(value)
        m.set_output(direction, power)

    def set_motor_function(self, name, direction, on):
        # direction: "fwd" or "rev", on: True/False (button press)
        m = self.motor_functions.get(name)
        if not m:
            return
        power = 1.0 if on else 0.0
        m.set_output(direction, power)

    def set_function(self, name, value):
        # value: True/False (on/off)
        if self.function_controller:
            self.function_controller.set_function(name, value)
            self.functions[name] = value

    def stop_axis(self, name):
        m = self.axis_motors.get(name)
        if m:
            m.stop()

    def stop_motor_function(self, name):
        m = self.motor_functions.get(name)
        if m:
            m.stop()

    def stop_all(self):
        for m in list(self.axis_motors.values()) + list(self.motor_functions.values()):
            m.stop()
        if self.function_controller:
            for fname in self.functions:
                self.function_controller.set_function(fname, False)

    # --------------------
    # Public API
    # --------------------

    def update_min_power(self, name, min_value):
        print(f"[DEBUG] update_min_power called: name={name}, min_value={min_value}")
        all_motors = {}
        all_motors.update(self.axis_motors)
        all_motors.update(self.motor_functions)
        if name not in all_motors:
            print(f"[DEBUG] Motor {name} not found in axis_motors or motor_functions!")
            return False

        try:
            min_val = int(min_value)
        except Exception as e:
            print(f"[DEBUG] Exception converting min_value: {e}")
            return False

        # clamp reasonable range
        min_val = max(0, min(MAX_DUTY - 1, min_val))

        # update instance
        all_motors[name].min_power = min_val
        print(f"[DEBUG] {name}.min_power set to {min_val}")

        # persist to config
        cfg = load_config()
        print(f"[DEBUG] Config before update: {cfg}")
        mm = cfg.get("motor_min")
        if not isinstance(mm, dict):
            mm = {}
        mm[name] = min_val
        cfg["motor_min"] = mm
        try:
            save_config(cfg)
            print(f"[DEBUG] Config after update: {cfg}")
        except Exception as e:
            print(f"[DEBUG] Exception saving config: {e}")

        return True

    # --------------------
    # Watchdog (Timer IRQ)
    # --------------------
    async def watchdog(self):
        # Async watchdog task; periodically checks motors and stops any that
        # haven't been updated within self.timeout_ms. This must be scheduled on
        # the same asyncio loop that handles WebSocket/HTTP so PWM calls are
        # executed in the same thread and avoid IRQ concurrency.
        try:
            import uasyncio as asyncio
        except Exception:
            try:
                import asyncio
            except Exception:
                return

        interval = min(0.1, self.timeout_ms / 1000.0)
        while True:
            now = time.ticks_ms()
            for m in list(self.axis_motors.values()) + list(self.motor_functions.values()):
                if m.running:
                    try:
                        if time.ticks_diff(now, m.last_update_ms) > self.timeout_ms:
                            m.stop()
                    except Exception:
                        pass
            try:
                await asyncio.sleep(interval)
            except Exception:
                break

motor_controller = MotorController()
