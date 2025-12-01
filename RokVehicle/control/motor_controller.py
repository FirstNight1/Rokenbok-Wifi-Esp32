# control/motor_controller.py


import time
from machine import Pin, PWM
from variables.vars_store import load_config, save_config
from variables.vehicle_types import VEHICLE_TYPES
try:
    from control.power_manager import power_manager
except Exception:
    power_manager = None
try:
    from control.function_controller import FunctionController
except Exception:
    FunctionController = None

PWM_FREQ = 2000
MAX_DUTY = 65535

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
        for name, m in {**self.axis_motors, **self.motor_functions}.items():
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

    def update_min_power(self, name, min_value):
        # ...existing code...

    # --------------------
    # Public API
    # --------------------

    # (Obsolete set_motor, stop_motor, stop_all removed; use set_axis, set_motor_function, set_function, stop_axis, stop_motor_function, stop_all)

    def update_min_power(self, name, min_value):
        """Update the minimum duty for a named motor and persist in config."""
        all_motors = {**self.axis_motors, **self.motor_functions}
        if name not in all_motors:
            return False

        try:
            min_val = int(min_value)
        except Exception:
            return False

        # clamp reasonable range
        min_val = max(0, min(MAX_DUTY - 1, min_val))

        # update instance
        all_motors[name].min_power = min_val

        # persist to config
        cfg = load_config()
        mm = cfg.get("motor_min") or {}
        mm[name] = min_val
        cfg["motor_min"] = mm
        try:
            save_config(cfg)
        except Exception:
            pass

        return True

    # --------------------
    # Watchdog (Timer IRQ)
    # --------------------


    async def watchdog(self):
        """Async watchdog task; periodically checks motors and stops any that
        haven't been updated within self.timeout_ms. This must be scheduled on
        the same asyncio loop that handles WebSocket/HTTP so PWM calls are
        executed in the same thread and avoid IRQ concurrency.
        """
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
# On startup, if not asleep, ensure D8 is high
if power_manager and not power_manager.is_asleep():
    power_manager.wake()
