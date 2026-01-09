# control/function_controller.py
# Simple on/off logic function controller for non-motor functions (e.g., lights, siren, etc.)

# TODO - update for actual usage (emergency lights on 2 pins, siren via audio I2S, etc.)


class FunctionController:
    def __init__(self, pin_map):
        # pin_map: {function_name: pin_number}
        self.pin_map = pin_map
        self.state = {name: False for name in pin_map}

    def set_function(self, name, value):
        # value: True (on) or False (off)
        if name not in self.pin_map:
            raise ValueError("Unknown function: {}".format(name))
        self.state[name] = bool(value)
        self._apply(name)

    def get_function(self, name):
        return self.state.get(name, False)

    def _apply(self, name):
        # TODO: Implement actual pin control (e.g., using machine.Pin for MicroPython)
        # For now, just a placeholder
        pass


# Example usage:
# fc = FunctionController({'lights': 12, 'siren': 13})
# fc.set_function('lights', True)
# fc.set_function('siren', False)
