# control/motor_controller.py

import time
from machine import Pin, PWM
from variables.vars_store import load_config, save_config
from variables.vehicle_types import VEHICLE_TYPES

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

        mapping = vinfo.get("motor_map", {})   # FIXED

        self.motors = {
            name: Motor(name, info["motor"], info.get("reversed", False))
            for name, info in mapping.items()
        }

        # Load per-motor min power values from config (if present)
        motor_min_cfg = cfg.get("motor_min", {})
        for name, m in self.motors.items():
            # Use stored value or default 40000
            try:
                m.min_power = int(motor_min_cfg.get(name, 40000))
            except Exception:
                m.min_power = 40000

        # watchdog timeout (ms)
        self.timeout_ms = 200   # motors must receive update every 200ms

        # NOTE: previously a hardware Timer IRQ called back into Python and
        # manipulated PWM objects from interrupt context. That can crash the
        # MicroPython runtime (and USB REPL). Instead we provide an asyncio-
        # friendly watchdog coroutine `watchdog()` which should be scheduled
        # on the async loop so all PWM calls happen in the same thread.

    # --------------------
    # Public API
    # --------------------

    def set_motor(self, name, direction, power):
        m = self.motors.get(name)
        if not m:
            return  # ignore invalid names
        m.set_output(direction, power)

    def stop_motor(self, name):
        m = self.motors.get(name)
        if m:
            m.stop()

    def stop_all(self):
        for m in self.motors.values():
            m.stop()

    def update_min_power(self, name, min_value):
        """Update the minimum duty for a named motor and persist in config."""
        if name not in self.motors:
            return False

        try:
            min_val = int(min_value)
        except Exception:
            return False

        # clamp reasonable range
        min_val = max(0, min(MAX_DUTY - 1, min_val))

        # update instance
        self.motors[name].min_power = min_val

        # persist to config
        cfg = load_config()
        mm = cfg.get("motor_min") or {}
        mm[name] = min_val
        cfg["motor_min"] = mm
        try:
            save_config(cfg)
        except Exception:
            # best-effort: ignore save errors
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

        # check interval: smaller than timeout to ensure timely stop
        interval = min(0.1, self.timeout_ms / 1000.0)
        while True:
            now = time.ticks_ms()
            for m in self.motors.values():
                if m.running:
                    try:
                        if time.ticks_diff(now, m.last_update_ms) > self.timeout_ms:
                            m.stop()
                    except Exception:
                        # best-effort: ignore errors per motor
                        pass
            try:
                await asyncio.sleep(interval)
            except Exception:
                # if sleep fails, break out
                break

motor_controller = MotorController()
