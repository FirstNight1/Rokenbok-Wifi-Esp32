import machine
import time
import network

# LED Configuration
LED_PIN = 9  # Pin D10 (GPIO9)


class LEDStatusManager:
    def __init__(self):
        try:
            # Use simple digital pin instead of PWM
            self.led_pin = machine.Pin(LED_PIN, machine.Pin.OUT)
            self.led_pin.off()
            self.led_available = True
        except Exception as e:
            print(f"LED initialization failed: {e}")
            self.led_available = False
            self.led_pin = None

        # Simple override state
        self.override_active = False
        self.override_state = False
        self.startup_blinking = False
        self.blink_timer = None
        self.blink_state = False
        self.ap_start_time = None

    def startup_blink(self):
        """Start continuous blinking LED on startup - call from main on initial startup"""
        if not self.led_available:
            return

        self.startup_blinking = True
        self.blink_state = False

        # Start timer for continuous blinking (disconnected/connecting pattern)
        if self.blink_timer is None:
            try:
                self.blink_timer = machine.Timer(0)
                self.blink_timer.init(
                    period=500,  # 0.5 second intervals (half on, half off)
                    mode=machine.Timer.PERIODIC,
                    callback=self._blink_callback,
                )
            except Exception as e:
                print(f"Failed to start blink timer: {e}")

    def _blink_callback(self, timer):
        """Timer callback for blinking patterns"""
        if not self.led_available or self.override_active:
            return

        # Check current WiFi status and set appropriate pattern
        sta = network.WLAN(network.STA_IF)
        ap = network.WLAN(network.AP_IF)

        if sta.active() and sta.isconnected():
            # STA connected - solid on
            self.led_pin.on()
            return

        if ap.active():
            # AP mode - check if in first 10 seconds
            current_time = time.time()
            if self.ap_start_time is None:
                self.ap_start_time = current_time

            if (current_time - self.ap_start_time) < 10:
                # First 10 seconds of AP mode: 0.9s on, 0.1s off
                # We need to change timer frequency for this pattern
                if hasattr(self, "_ap_blink_phase"):
                    if self._ap_blink_phase:
                        self.led_pin.off()
                        self._ap_blink_phase = False
                        # Reconfigure for 100ms off period
                        self.blink_timer.init(
                            period=100,
                            mode=machine.Timer.PERIODIC,
                            callback=self._blink_callback,
                        )
                    else:
                        self.led_pin.on()
                        self._ap_blink_phase = True
                        # Reconfigure for 900ms on period
                        self.blink_timer.init(
                            period=900,
                            mode=machine.Timer.PERIODIC,
                            callback=self._blink_callback,
                        )
                else:
                    # Initialize AP blink phase
                    self._ap_blink_phase = True
                    self.led_pin.on()
                    self.blink_timer.init(
                        period=900,
                        mode=machine.Timer.PERIODIC,
                        callback=self._blink_callback,
                    )
            else:
                # After 10 seconds in AP mode - solid on
                self.led_pin.on()
                return
        else:
            # Not connected - continue startup blink pattern (0.5s on/off)
            self.blink_state = not self.blink_state
            if self.blink_state:
                self.led_pin.on()
            else:
                self.led_pin.off()

    def set_wifi_status(self):
        """Check WiFi status and set LED pattern accordingly - call from main after WiFi setup"""
        if not self.led_available or self.override_active:
            return

        # Stop startup blinking and update patterns
        sta = network.WLAN(network.STA_IF)
        ap = network.WLAN(network.AP_IF)

        # Reset AP start time when setting status
        if ap.active():
            self.ap_start_time = time.time()

        # STA connected - full on and stop timer
        if sta.active() and sta.isconnected():
            self._stop_startup_blink()
            self.led_pin.on()
            return

        # AP mode - record start time and continue with timer for pattern
        if ap.active():
            self.ap_start_time = time.time()
            # Timer will handle the AP mode pattern
            return

        # Neither connected - turn off and stop timer
        self._stop_startup_blink()
        self.led_pin.off()

    def _stop_startup_blink(self):
        """Stop the startup blinking timer"""
        if self.blink_timer is not None:
            try:
                self.blink_timer.deinit()
                self.blink_timer = None
                self.startup_blinking = False
                self._ap_blink_phase = None
            except Exception as e:
                print(f"Failed to stop blink timer: {e}")

    def set_override(self, enabled, state=None):
        """Admin override control"""
        if not self.led_available:
            return

        self.override_active = enabled
        if enabled and state is not None:
            self.override_state = bool(state)
            if self.override_state:
                self.led_pin.on()
            else:
                self.led_pin.off()
        elif not enabled:
            # Return to auto mode - check WiFi status
            self.set_wifi_status()

    def get_override_status(self):
        """Get current override status for admin page"""
        return {"active": self.override_active, "state": self.override_state}


# Global instance
_led_manager = None


def init_led_status():
    """Initialize LED status management"""
    global _led_manager
    if _led_manager is None:
        _led_manager = LEDStatusManager()
    return _led_manager


def startup_blink():
    """Startup blink - call from main"""
    global _led_manager
    if _led_manager is not None:
        _led_manager.startup_blink()


def set_wifi_status():
    """Set WiFi status - call from main after WiFi setup"""
    global _led_manager
    if _led_manager is not None:
        _led_manager.set_wifi_status()


def get_led_manager():
    """Get the LED manager instance for admin page"""
    return _led_manager
