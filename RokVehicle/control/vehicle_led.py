import machine
import time

# Available pins for vehicle LEDs (including busy LED) - ESP32-S3 pinout mapping
VEHICLE_LED_PINS = {
    1: "D0", 2: "D1", 3: "D2", 4: "D3", 5: "D4", 6: "D5",
    43: "D6", 44: "D7", 7: "D8", 8: "D9", 9: "D10", 10: "D11",
    42: "D12", 41: "D13", 21: "User LED"
}

# Special value for "No Pin" option
NO_PIN = -1


class VehicleLEDManager:
    """Vehicle-specific LED controller for busy status and vehicle function LEDs"""
    
    def __init__(self, busy_pin=None):
        self.busy_pin_num = busy_pin
        self.busy_pin = None
        self.busy_enabled = False
        self.busy_timer = None
        self.busy_state = False
        self.vehicle_busy = False
        self.override_active = False
        self.override_state = False
        
        # GPIO21 is active low (HIGH=OFF, LOW=ON)
        self.active_low = (busy_pin == 21 if busy_pin is not None else False)
        
        # Initialize busy LED if pin provided
        if busy_pin is not None and busy_pin != NO_PIN:
            self._init_busy_led(busy_pin)
            
    def _led_on(self):
        """Turn LED on (handles active low/high)"""
        if self.busy_pin:
            if self.active_low:
                self.busy_pin.off()  # LOW turns on active-low LED
            else:
                self.busy_pin.on()   # HIGH turns on active-high LED
                
    def _led_off(self):
        """Turn LED off (handles active low/high)"""
        if self.busy_pin:
            if self.active_low:
                self.busy_pin.on()   # HIGH turns off active-low LED
            else:
                self.busy_pin.off()  # LOW turns off active-high LED

    def _init_busy_led(self, pin):
        """Initialize the busy LED pin"""
        try:
            # Check if network LED is using this pin in shared mode
            if self._is_pin_shared_with_network(pin):

                self.busy_enabled = False
                self.busy_pin = None
                return
                
            self.busy_pin_num = pin
            # GPIO21 is active low (HIGH=OFF, LOW=ON)
            self.active_low = (pin == 21)
            self.busy_pin = machine.Pin(pin, machine.Pin.OUT)
            self._led_off()  # Turn LED off using correct polarity
            self.busy_enabled = True
        except Exception as e:
            self.busy_enabled = False
            self.busy_pin = None

    def _is_pin_shared_with_network(self, pin):
        """Check if this pin is being used by network LED in shared mode"""
        try:
            from RokCommon.control.network_led import get_network_led
            network_led = get_network_led()
            if network_led and hasattr(network_led, 'shared_mode'):
                return (network_led.shared_mode and 
                       network_led.led_available and 
                       network_led.led_pin_num == pin)
        except Exception:
            pass
        return False

    def deinit(self):
        """Deinitialize the busy LED"""
        try:
            if self.busy_timer is not None:
                self.busy_timer.deinit()
                self.busy_timer = None
            if self.busy_pin is not None:
                self._led_off()
                self.busy_pin = None
            self.busy_enabled = False
        except Exception as e:
            pass

    def reinit_busy_led(self, new_pin):
        """Reinitialize busy LED with a new pin number"""
        try:
            self.deinit()
            if new_pin is not None and new_pin != NO_PIN:
                # Check if this pin is shared with network LED
                if self._is_pin_shared_with_network(new_pin):

                    self.busy_enabled = False
                    return
                self._init_busy_led(new_pin)
            else:
                self.busy_enabled = False
        except Exception as e:
            self.busy_enabled = False

    def start_busy_monitoring(self):
        """Start the busy LED monitoring timer"""
        if not self.busy_enabled or self.override_active:
            return
            
        # Double-check that we're not in shared mode
        if self._is_pin_shared_with_network(self.busy_pin_num):
            return
            
        try:
            # Start timer to check vehicle status every 2 seconds
            self.busy_timer = machine.Timer(1)
            self.busy_timer.init(
                period=2000,  # 2 seconds
                mode=machine.Timer.PERIODIC,
                callback=self._busy_callback
            )
        except Exception as e:
            pass

    def stop_busy_monitoring(self):
        """Stop the busy LED monitoring timer"""
        try:
            if self.busy_timer is not None:
                self.busy_timer.deinit()
                self.busy_timer = None
            if self.busy_pin is not None:
                self._led_off()
        except Exception as e:
            pass

    def _busy_callback(self, timer):
        """Timer callback to update busy LED status"""
        if not self.busy_enabled or self.override_active:
            return

        # Safety check: if pin is now in shared mode, stop monitoring
        if self._is_pin_shared_with_network(self.busy_pin_num):
            self.stop_busy_monitoring()
            return

        try:
            # Check if vehicle is busy (simplified check for now)
            # This can be expanded to check actual vehicle busy status
            current_busy = self._check_vehicle_busy()
            
            if self.vehicle_busy:
                # Vehicle is busy - solid on
                self._led_on()
            else:
                # Vehicle available - toggle every second (2 sec timer, so alternate)
                self.busy_state = not self.busy_state
                if self.busy_state:
                    self._led_on()
                else:
                    self._led_off()
                    
        except Exception as e:
            print(f"Busy LED callback error: {e}")

    def _check_vehicle_busy(self):
        """Check if vehicle is currently busy - can be expanded later"""
        try:
            # For now, simple check - can be enhanced to check:
            # - WebSocket connections
            # - Motor activity
            # - Current operations
            
            # Placeholder logic - check if any motors are active
            # This is a simplified implementation
            from control.motor_controller import motor_controller
            if hasattr(motor_controller, 'is_busy'):
                return motor_controller.is_busy()
            else:
                # Default: vehicle is available
                return False
        except Exception:
            # If unable to check, assume not busy
            return False

    def set_vehicle_busy(self, busy):
        """Manually set vehicle busy status"""
        if not self.busy_enabled:
            return
        self.vehicle_busy = busy
        if busy:
            self._led_on()
        # If not busy, let the timer handle the blinking

    def set_busy_override(self, enabled, state=None):
        """Admin override control for busy LED testing"""
        if not self.busy_enabled:
            return

        self.override_active = enabled
        if enabled and state is not None:
            self.override_state = bool(state)
            if self.override_state:
                self._led_on()
            else:
                self._led_off()
        elif not enabled:
            # Return to auto mode
            if self.busy_timer is None:
                self.start_busy_monitoring()

    def get_busy_status(self):
        """Get current busy LED status for admin interface"""
        return {
            "enabled": self.busy_enabled,
            "pin": self.busy_pin_num,
            "busy": self.vehicle_busy,
            "override_active": self.override_active,
            "override_state": self.override_state,
            "shared_mode_conflict": self._is_pin_shared_with_network(self.busy_pin_num) if self.busy_pin_num else False
        }

    def is_busy_enabled(self):
        """Check if busy LED is available and enabled"""
        return self.busy_enabled and not self.override_active


# Global instance
vehicle_led = None

def init_vehicle_led(busy_pin=None):
    """Initialize the vehicle LED manager"""
    global vehicle_led
    if vehicle_led is not None:
        vehicle_led.deinit()
    vehicle_led = VehicleLEDManager(busy_pin)
    return vehicle_led

def get_vehicle_led():
    """Get the global vehicle LED manager instance"""
    return vehicle_led