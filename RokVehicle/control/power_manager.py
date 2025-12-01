# control/power_manager.py
# Handles vehicle shutdown/sleep and wake logic, including D8 (Pin 7) control

import time
try:
    from machine import Pin
except ImportError:
    Pin = None

D8_PIN = 7  # D8 = GPIO7 on ESP32-S3

class PowerManager:
    def __init__(self):
        self.d8 = Pin(D8_PIN, Pin.OUT) if Pin else None
        self.asleep = False
        self.last_active = time.time()

    def shutdown(self):
        if self.d8:
            self.d8.value(0)  # Pull D8 low to disable motor controllers
        self.asleep = True
        self.last_active = time.time()

    def wake(self):
        if self.d8:
            self.d8.value(1)  # Pull D8 high to enable motor controllers
        self.asleep = False
        self.last_active = time.time()

    def is_asleep(self):
        return self.asleep

    def mark_active(self):
        self.last_active = time.time()

    def should_sleep(self, timeout=300):
        # timeout in seconds (default 5 min)
        return (not self.asleep) and (time.time() - self.last_active > timeout)

# Singleton
power_manager = PowerManager()
