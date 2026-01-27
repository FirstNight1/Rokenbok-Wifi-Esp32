# control/function_controller.py
# Simple on/off logic function controller for non-motor functions (e.g., lights, siren, etc.)
#
# The frontend control will include a function on or function off toggle with the control packets,
# which control_processor will send here.


# TODO - update for actual usage (emergency lights on 2 pins, siren via audio I2S, etc.)


class FunctionController:
    def __init__(self, pin_map):
        # pin_map: {function_name: pin_number}
        self.pin_map = pin_map
        self.state = {name: False for name in pin_map}
        self.pins = {}
        
        # Initialize pins
        try:
            from machine import Pin
            for name, pin_num in pin_map.items():
                self.pins[name] = Pin(pin_num, Pin.OUT)
                self.pins[name].value(0)  # Start with all functions off
        except Exception as e:
            print(f"Function controller pin initialization error: {e}")

    def set_function(self, name, value):
        """Set a logic function on or off - called by control_processor"""
        if name not in self.pin_map:
            print(f"Unknown function: {name}")
            return
        
        self.state[name] = bool(value)
        self._apply(name)

    def get_function(self, name):
        """Get current state of a function"""
        return self.state.get(name, False)

    def _apply(self, name):
        """Apply the state to the actual pin"""
        try:
            if name in self.pins:
                self.pins[name].value(1 if self.state[name] else 0)
        except Exception as e:
            print(f"Function controller pin control error for {name}: {e}")
    
    def turn_all_off(self):
        """Turn off all functions"""
        for name in self.state:
            self.set_function(name, False)


# Example usage:
# fc = FunctionController({'lights': 12, 'siren': 13})
# fc.set_function('lights', True)
# fc.set_function('siren', False)
