import machine
import time
import network

# Default LED Pin - can be overridden per project
DEFAULT_LED_PIN = 9  # Pin D10 (GPIO9)

# Available pins for network status LED (ESP32-S3 pinout mapping)
NETWORK_LED_PINS = {
    1: "D0", 2: "D1", 3: "D2", 4: "D3", 5: "D4", 6: "D5",
    43: "D6", 44: "D7", 7: "D8", 8: "D9", 9: "D10", 10: "D11",
    42: "D12", 41: "D13", 21: "User LED"
}


class NetworkLEDManager:
    """Network status LED controller for startup sequence and connection status"""
    
    def __init__(self, pin=None, shared_mode=False):
        self.led_pin_num = pin if pin is not None else DEFAULT_LED_PIN
        
        # GPIO21 is active low (HIGH=OFF, LOW=ON)
        self.active_low = (self.led_pin_num == 21)
        
        try:
            # Use simple digital pin instead of PWM
            self.led_pin = machine.Pin(self.led_pin_num, machine.Pin.OUT)
            self._led_off()  # Turn LED off using correct polarity
            self.led_available = True
        except Exception as e:

            self.led_available = False
            self.led_pin = None

        # State management
        self.override_active = False
        self.override_state = False
        self.startup_blinking = False
        self.blink_timer = None
        self.blink_state = False
        self._ap_blink_phase = None
        
        # Shared mode functionality (network LED + busy LED on same pin)
        self.shared_mode = shared_mode
        self.network_final_state_reached = False
        self.transition_timer = None
        self.in_busy_mode = False
        self.vehicle_busy = False
        self.busy_blink_state = False
        
    def _led_on(self):
        """Turn LED on (handles active low/high)"""
        if self.led_pin:
            if self.active_low:
                self.led_pin.off()  # LOW turns on active-low LED
            else:
                self.led_pin.on()   # HIGH turns on active-high LED
                
    def _led_off(self):
        """Turn LED off (handles active low/high)"""
        if self.led_pin:
            if self.active_low:
                self.led_pin.on()   # HIGH turns off active-low LED
            else:
                self.led_pin.off()  # LOW turns off active-high LED

    def deinit(self):
        """Deinitialize the LED pin and timer"""
        try:
            if self.blink_timer is not None:
                self.blink_timer.deinit()
                self.blink_timer = None
            if self.transition_timer is not None:
                self.transition_timer.deinit()
                self.transition_timer = None
            if self.led_pin is not None:
                self._led_off()
                self.led_pin = None
            # Reset all state variables
            self.led_available = False
            self.override_active = False
            self.startup_blinking = False
            self.network_final_state_reached = False
            self.in_busy_mode = False
            self._ap_blink_phase = None
            # Network LED: Complete deinitialization
        except Exception as e:
            print(f"Network LED deinit error: {e}")

    def reinit_with_pin(self, new_pin, shared_mode=False):
        """Reinitialize LED with a new pin number and force status update"""
        try:
            self.deinit()
            self.led_pin_num = new_pin
            # GPIO21 is active low (HIGH=OFF, LOW=ON)
            self.active_low = (new_pin == 21)
            self.led_pin = machine.Pin(new_pin, machine.Pin.OUT)
            self._led_off()
            self.led_available = True
            self.shared_mode = shared_mode
            self.network_final_state_reached = False
            self.in_busy_mode = False
            print(f"Network LED reinitialized on pin {new_pin}, shared_mode={shared_mode}")
            
            # Start fresh with the current WiFi status
            self._start_fresh_sequence()
        except Exception as e:
            print(f"LED reinit failed on pin {new_pin}: {e}")
            self.led_available = False

    def _start_fresh_sequence(self):
        """Start a fresh LED sequence based on current WiFi status"""
        if not self.led_available:
            return
            
        # Check current WiFi interfaces
        sta = network.WLAN(network.STA_IF)
        ap = network.WLAN(network.AP_IF)

        if sta.active() and sta.isconnected():
            # Already connected to STA - go straight to solid on
            self._led_on()
            if self.shared_mode:
                print("Network LED: STA already connected - starting transition timer")
                self._check_transition_to_busy()
            else:
                print("Network LED: STA already connected - solid on indefinitely")
        elif ap.active():
            # AP mode active - start the AP blink pattern
            print("Network LED: AP mode active - starting blink pattern")
            self.start_startup_blink()
        else:
            # No connection - start startup blink sequence
            print("Network LED: No connection - starting startup sequence")
            self.start_startup_blink()

    def _force_status_update(self):
        """Force an immediate update of LED status with full pattern activation"""
        if not self.led_available:
            return
            
        # Check WiFi interfaces
        sta = network.WLAN(network.STA_IF)
        ap = network.WLAN(network.AP_IF)

        # STA connected - show immediate solid on
        if sta.active() and sta.isconnected():
            self._stop_startup_blink()
            self._led_on()
            if self.shared_mode:
                # Start transition in shared mode
                self._start_transition_to_busy()
            # else: solid on indefinitely in normal mode
            return

        # AP mode - start AP pattern immediately
        if ap.active():
            self.start_startup_blink()  # This will trigger the AP pattern
            return

        # Neither connected - turn off
        self._stop_startup_blink()
        self._led_off()

    def start_startup_blink(self):
        """Start the startup blinking pattern during boot sequence"""
        if not self.led_available:
            return
            
        self.startup_blinking = True
        self.blink_state = False
        
        try:
            # Start with 0.5s on/off pattern during startup
            self.blink_timer = machine.Timer(0)
            self.blink_timer.init(
                period=500,
                mode=machine.Timer.PERIODIC,
                callback=self._blink_callback
            )
        except Exception as e:
            print(f"Failed to start startup blink: {e}")

    def _blink_callback(self, timer):
        """Timer callback for LED blinking patterns"""
        if not self.led_available or self.override_active:
            return

        # If in busy mode, handle busy LED logic
        if self.in_busy_mode:
            self._handle_busy_mode()
            return

        # Check WiFi interfaces
        sta = network.WLAN(network.STA_IF)
        ap = network.WLAN(network.AP_IF)

        # STA connected - go steady on and stop this timer
        if sta.active() and sta.isconnected():
            self._led_on()
            self._stop_startup_blink()
            # Only check transition to busy if in shared mode
            if self.shared_mode:
                self._check_transition_to_busy()

            return

        # AP mode active - continue AP pattern indefinitely (never steady state)
        if ap.active():
            if hasattr(self, '_ap_blink_phase'):
                if self._ap_blink_phase:
                    self._led_off()
                    self._ap_blink_phase = False
                    # Reconfigure for 100ms off period
                    self.blink_timer.init(
                        period=100,
                        mode=machine.Timer.PERIODIC,
                        callback=self._blink_callback,
                    )
                else:
                    self._led_on()
                    self._ap_blink_phase = True
                    # Reconfigure for 900ms on period
                    self.blink_timer.init(
                        period=900,
                        mode=machine.Timer.PERIODIC,
                        callback=self._blink_callback,
                    )
                    # Only check for transition to busy mode if in shared mode
                    if self.shared_mode:
                        self._check_transition_to_busy()
            else:
                # Initialize AP blink phase (900ms on, 100ms off)
                self._ap_blink_phase = True
                self._led_on()
                self.blink_timer.init(
                    period=900,
                    mode=machine.Timer.PERIODIC,
                    callback=self._blink_callback,
                )
        else:
            # Not connected - continue startup blink pattern (0.5s on/off)
            self.blink_state = not self.blink_state
            if self.blink_state:
                self._led_on()
            else:
                self._led_off()

    def _check_transition_to_busy(self):
        """Check if we should start transition to busy mode (shared mode only)"""
        if not self.shared_mode or self.network_final_state_reached:
            return
            
        self.network_final_state_reached = True

        # Start 30-second transition timer
        try:
            self.transition_timer = machine.Timer(2)  # Use timer 2 for transition
            self.transition_timer.init(
                period=30000,  # 30 seconds
                mode=machine.Timer.ONE_SHOT,
                callback=self._transition_to_busy
            )
        except Exception as e:
            print(f"Failed to start transition timer: {e}")

    def _transition_to_busy(self, timer):
        """Transition from network LED to busy LED mode"""
        print("Network LED: Transitioning to busy mode")
        self.in_busy_mode = True
        
        # Stop network LED blinking
        if self.blink_timer is not None:
            self.blink_timer.deinit()
            self.blink_timer = None
            
        # Start busy LED monitoring (2-second intervals)
        try:
            self.blink_timer = machine.Timer(0)  # Reuse timer 0 for busy mode
            self.blink_timer.init(
                period=2000,  # 2 seconds
                mode=machine.Timer.PERIODIC,
                callback=self._blink_callback
            )
        except Exception as e:
            print(f"Failed to start busy monitoring: {e}")

    def _handle_busy_mode(self):
        """Handle busy LED logic when in shared mode"""
        try:
            # Check if vehicle is busy (simplified check for now)
            current_busy = self._check_vehicle_busy()
            
            if current_busy != self.vehicle_busy:
                self.vehicle_busy = current_busy
            
            if self.vehicle_busy:
                # Vehicle is busy - solid on
                self._led_on()
            else:
                # Vehicle available - toggle every call (2 sec timer, so alternate)
                self.busy_blink_state = not self.busy_blink_state
                if self.busy_blink_state:
                    self._led_on()
                else:
                    self._led_off()
                    
        except Exception as e:
            print(f"Busy LED callback error: {e}")

    def _check_vehicle_busy(self):
        """Check if vehicle is currently busy"""
        try:
            # Import here to avoid circular imports
            from control.motor_controller import get_motor_controller
            motor_controller = get_motor_controller()
            if motor_controller and hasattr(motor_controller, 'is_busy'):
                return motor_controller.is_busy()
            else:
                # Fallback: try to get busy status directly from web server
                try:
                    from web.web_server import get_effective_busy_status
                    return get_effective_busy_status()
                except Exception:
                    # Default: vehicle is available
                    return False
        except Exception:
            # If unable to check, assume not busy
            return False

    def set_wifi_status(self):
        """Check WiFi status and set LED pattern accordingly - call from main after WiFi setup"""
        if not self.led_available or self.override_active:
            return

        # Check WiFi interfaces
        sta = network.WLAN(network.STA_IF)
        ap = network.WLAN(network.AP_IF)

        # STA connected - steady on
        if sta.active() and sta.isconnected():
            self._stop_startup_blink()
            self._led_on()

            return

        # AP mode - continue pattern indefinitely (never go steady state)
        if ap.active():
            if not self.startup_blinking:
                self.start_startup_blink()
                print("Network LED: AP mode - starting blink pattern")
            # Timer will handle the AP mode pattern continuously
            return

        # Neither connected - turn off and stop timer
        self._stop_startup_blink()
        self._led_off()
        print("Network LED: No connection - turned off")

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
        else:
            pass  # Timer not running

    def set_override(self, enabled, state=None):
        """Admin override control for testing"""
        if not self.led_available:
            return

        self.override_active = enabled
        if enabled and state is not None:
            self.override_state = bool(state)
            if self.override_state:
                self._led_on()
            else:
                self._led_off()
        elif not enabled:
            # Return to auto mode - check WiFi status
            self.set_wifi_status()

    def get_override_status(self):
        """Get current override status for admin interfaces"""
        return {"active": self.override_active, "state": self.override_state}

    def is_enabled(self):
        """Check if LED is available and enabled"""
        return self.led_available and not self.override_active


# Global instance - will be initialized by each project
network_led = None

def init_network_led(pin=None, shared_mode=False):
    """Initialize the network status LED manager"""
    global network_led
    if network_led is not None:
        network_led.deinit()
    network_led = NetworkLEDManager(pin, shared_mode)
    return network_led

def get_network_led():
    """Get the global network LED manager instance"""
    return network_led