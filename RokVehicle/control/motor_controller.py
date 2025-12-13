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

    def set_output_axis(self, direction, power):
        # Axis motor: power is 0..1, mapped to [min_power..MAX_DUTY]
        if power <= 0:
            duty = 0
        else:
            min_p = self.min_power if self.min_power is not None else 40000
            p = max(0.0, min(1.0, float(power)))
            duty = int(min_p + p * (MAX_DUTY - min_p))

        forward = direction == "fwd"
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

    def set_output_function(self, direction, on):
        # Function motor: on=True sets min_power (with fallback), off sets 0
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

    def set_output(self, direction, value, mode="axis"):
        # Dispatcher: mode is "axis" or "function"
        if mode == "function":
            self.set_output_function(direction, bool(value))
        else:
            self.set_output_axis(direction, value)


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
        cfg = load_config()
        # MicroPython: ensure assignments is a plain dict, not a subclass
        cfg["motor_numbers"] = dict((str(k), int(v)) for k, v in assignments.items())
        save_config(cfg)
        # Deinit all PWM channels before re-instantiating
        self.deinit_all()
        # Re-instantiate the global motor_controller so all references are fresh
        import sys

        thismod = sys.modules[__name__]
        thismod.motor_controller = MotorController()
        return True

    def stop_motor(self, name):
        """Stop a motor by name, whether axis or function motor."""
        if name in self.axis_motors:
            self.axis_motors[name].stop()
        elif name in self.motor_functions:
            self.motor_functions[name].stop()

    def set_motor(self, name, direction, power):
        # Expect power in 0-100 range
        if name in self.axis_motors:
            # Convert 0-100 to 0-1 for internal motor processing
            normalized_power = power / 100.0
            self.axis_motors[name].set_output(direction, normalized_power, mode="axis")
        elif name in self.motor_functions:
            # For function motors, treat any power >= 1 as ON, else OFF
            m = self.motor_functions[name]
            m.set_output(direction, power >= 1, mode="function")

    def __init__(self):
        cfg = load_config()
        vtype = cfg.get("vehicleType")
        vinfo = next((v for v in VEHICLE_TYPES if v["typeName"] == vtype), None)
        if not vinfo:
            raise ValueError("Vehicle type not found")

        # Get custom motor number mapping if present
        motor_numbers = cfg.get("motor_numbers", {})

        # Axis motors (continuous, axis-assignable)
        self.axis_motors = {}
        motor_reversed_cfg = cfg.get("motor_reversed", {})
        for idx, name in enumerate(vinfo.get("axis_motors", [])):
            # Use custom mapping if present, else default
            motor_num = int(motor_numbers.get(name, idx + 1))
            reversed_val = bool(motor_reversed_cfg.get(name, False))
            self.axis_motors[name] = Motor(name, motor_num, reversed=reversed_val)

        # Motor functions (button-assignable, fwd/rev, on/off)
        self.motor_functions = {}
        for idx, name in enumerate(vinfo.get("motor_functions", [])):
            motor_num = int(motor_numbers.get(name, idx + 3))
            reversed_val = bool(motor_reversed_cfg.get(name, False))
            self.motor_functions[name] = Motor(name, motor_num, reversed=reversed_val)

        # Logic functions (on/off pins, e.g., lights, siren)
        self.functions = {}
        if FunctionController and vinfo.get("functions"):
            pin_map = {fname: 10 + idx for idx, fname in enumerate(vinfo["functions"])}
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

        self.timeout_ms = 400

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
            for m in list(self.axis_motors.values()) + list(
                self.motor_functions.values()
            ):
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
