# control/control_processor.py
#
# Accepts incoming control packets from the frontend, and distributes commands to motor_controller and function_controller.
# Handles motor safety watchdog where if no control packet is received within a timeout, all motors are stopped.
# Handles function motor time-based travel safety/limiting, preventing over-travel of function motors.

import time
import uasyncio as asyncio
from RokCommon.variables.vars_store import get_config_value

class ControlProcessor:
    """
    Central control processor that handles:
    - Receiving control packets from frontend
    - Watchdog safety monitoring
    - Function motor timing and safety
    - Delegating motor commands to motor_controller
    - Delegating function commands to function_controller
    """
    
    def __init__(self, motor_controller=None, function_controller=None):
        self.motor_controller = motor_controller
        self.function_controller = function_controller
        
        # Watchdog tracking
        self.last_packet_time = time.ticks_ms()
        self.watchdog_timeout_ms = get_config_value("motor_safety_timeout_ms", 400)
        self.controls_active = False  # Track if controls are currently active
        
        # Function motor timing for travel safety
        self.function_motor_timers = {}
        
        # Cache for travel safety motor lookups to avoid repeated expensive traversals
        self._travel_safety_cache = {}
        
        # Current active controls state
        self.current_controls = {
            "axisMotors": {},
            "functionMotors": {},
            "logicFunctions": {}
        }
        
        # Start watchdog task
        self._watchdog_task = None
        self.start_watchdog()
    
    def start_watchdog(self):
        """Start the safety watchdog task"""
        if self._watchdog_task:
            try:
                self._watchdog_task.cancel()
            except:
                pass
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())
    
    async def _watchdog_loop(self):
        """Safety watchdog that stops all motors if no packets received"""
        while True:
            try:
                if not self.controls_active:
                    # No active controls - wait for control activity
                    await asyncio.sleep_ms(100)
                else:
                    # Normal watchdog monitoring - compare time since last packet and stop if timeout exceeded
                    now = time.ticks_ms()
                    time_since_packet = time.ticks_diff(now, self.last_packet_time)
                    
                    # If it has been longer than the timeout, stop motors and mark controls inactive
                    if time_since_packet > self.watchdog_timeout_ms:
                        # Only stop motors if they have non-zero power values
                        has_active_controls = self._has_active_motor_controls()
                        
                        if has_active_controls:
                            # Update timers one final time before stopping (for accurate timing)
                            self._update_function_motor_timers()
                            print(f"Control watchdog timeout ({time_since_packet}ms) - stopping all motors")
                            self.stop_all_motors()
                        
                        # Mark controls as inactive until next control packet
                        self.controls_active = False
                    
                    await asyncio.sleep_ms(100)  # Check every 100ms
                
            except Exception as e:
                print(f"Watchdog error: {e}")
                await asyncio.sleep_ms(100)
    
    def process_packet(self, packet):
        """Process a control packet with motor commands"""
        packet_start = time.ticks_ms()
        self.last_packet_time = packet_start
        self.controls_active = True  # Mark controls as active when packet received
        
        # Simple packet counter for logging
        if not hasattr(self, 'process_count'):
            self.process_count = 0
        self.process_count += 1
        
        # Extract function motors from packet for reuse
        function_motors = packet.get("functionMotors", {})
        
        # Update function motor timers only if function motors are present
        timer_start = time.ticks_ms()
        if function_motors or self.current_controls.get("functionMotors"):
            self._update_function_motor_timers(function_motors)
        timer_end = time.ticks_ms()
        
        # Process axis motors
        axis_start = time.ticks_ms()
        axis_motors = packet.get("axisMotors", {})
        for motor_name, motor_data in axis_motors.items():
            direction = motor_data.get("dir", "fwd")
            power = motor_data.get("power", 0)
            use_slow_mode = motor_data.get("useSlowMode", False)
            self.run_axis_motor(motor_name, direction, power, use_slow_mode)
        
        # Stop axis motors not in the active list
        current_axis = set(axis_motors.keys())
        previous_axis = set(self.current_controls.get("axisMotors", {}).keys())
        for motor_name in (previous_axis - current_axis):
            self.stop_axis_motor(motor_name)
        axis_end = time.ticks_ms()
        
        # Process function motors
        function_start = time.ticks_ms()
        for motor_name, motor_data in function_motors.items():
            direction = motor_data.get("dir", "fwd")
            # Inclusion in packet implies on=True
            self.run_function_motor(motor_name, direction)
        
        # Stop function motors not in the active list (using old state)
        current_function = set(function_motors.keys())
        previous_function = set(self.current_controls.get("functionMotors", {}).keys())
        for motor_name in (previous_function - current_function):
            self.stop_function_motor(motor_name)
        function_end = time.ticks_ms()
        
        # Update current control state
        self.current_controls = {
            "axisMotors": axis_motors,  # Direct assignment instead of copy
            "functionMotors": function_motors,
            "logicFunctions": packet.get("logicFunctions", {})
        }
        
        packet_end = time.ticks_ms()
        
        # Process logic functions
        logic_functions = packet.get("logicFunctions", {})
        for func_name, is_active in logic_functions.items():
            self.set_logic_function(func_name, is_active)
        
        # Stop logic functions not in the active list
        current_logic = set(logic_functions.keys())
        previous_logic = set(self.current_controls.get("logicFunctions", {}).keys())
        for func_name in (previous_logic - current_logic):
            self.set_logic_function(func_name, False)
        
        # If all controls are now zero/inactive, mark controls as inactive to disable watchdog
        if not self._has_active_motor_controls():
            self.controls_active = False
            
        # Processing complete - timing logging removed for cleaner output
        self.process_count += 1
    
    def run_axis_motor(self, name, direction, power_percentage, use_slow_mode):
        """Run an axis motor with specified parameters"""
        if self.motor_controller:
            try:
                self.motor_controller.run_motor(name, direction, power_percentage, use_slow_mode)
            except Exception as e:
                print(f"Error running axis motor {name}: {e}")
    
    def run_function_motor(self, name, direction):
        """Run a function motor with timing-based travel limits"""
        if self.motor_controller:
            try:
                # Check travel safety before running
                safety_check = self._check_function_motor_travel_safety(name, direction)
                if safety_check == "allowed":
                    self.motor_controller.run_motor(name, direction, 100, False)
                elif safety_check == "limit_reached":
                    # Actively stop the motor when limit is reached
                    print(f"Travel limit reached for {name} motor in {direction} direction - stopping motor")
                    self.motor_controller.stop_motor(name)
                elif safety_check == "locked":
                    print(f"Motor {name} is locked in {direction} direction")
                    self.motor_controller.stop_motor(name)
            except Exception as e:
                print(f"Error running function motor {name}: {e}")
    
    def set_logic_function(self, name, is_active):
        """Set a logic function on/off state"""
        if self.function_controller:
            try:
                self.function_controller.set_function(name, is_active)
            except Exception as e:
                print(f"Error setting logic function {name}: {e}")
    
    def stop_axis_motor(self, name):
        """Stop an axis motor"""
        try:
            self.run_axis_motor(name, "fwd", 0, False)
        except Exception as e:
            print(f"Error stopping axis motor {name}: {e}")
    
    def stop_function_motor(self, name):
        """Stop a function motor"""
        if self.motor_controller:
            try:
                self.motor_controller.run_motor(name, "fwd", 0, False)
            except Exception as e:
                print(f"Error stopping function motor {name}: {e}")
        
    def stop_all_motors(self):
        """Emergency stop all motors and functions"""
        # Stop all axis motors
        for motor_name in self.current_controls.get("axisMotors", {}):
            self.stop_axis_motor(motor_name)
        
        # Stop all function motors  
        for motor_name in self.current_controls.get("functionMotors", {}):
            self.stop_function_motor(motor_name)
        
        # Turn off all logic functions
        for func_name in self.current_controls.get("logicFunctions", {}):
            self.set_logic_function(func_name, False)
        
        # Clear current state
        self.current_controls = {"axisMotors": {}, "functionMotors": {}, "logicFunctions": {}}
    
    def _has_active_motor_controls(self):
        """Check if any motors have non-zero power or logic functions are active"""
        # Check axis motors for non-zero power
        for motor_data in self.current_controls.get("axisMotors", {}).values():
            if motor_data.get("power", 0) > 0:
                return True
        
        # Check function motors for active state (inclusion in packet means active)
        if self.current_controls.get("functionMotors", {}):
            return True
        
        # Check logic functions for active state
        for is_active in self.current_controls.get("logicFunctions", {}).values():
            if is_active:
                return True
        
        return False
    
    def _update_function_motor_timers(self, function_motors=None):
        """Update travel safety timers for function motors (optimized)"""
        # Early exit if no function motors and no existing timers
        motors_to_check = function_motors if function_motors is not None else self.current_controls.get("functionMotors", {})
        if not motors_to_check and not self.function_motor_timers:
            return
        
        now = time.ticks_ms()
        
        # Only process motors that actually have travel safety enabled
        for motor_name in motors_to_check:
            if motor_name not in self.function_motor_timers and self._motor_has_travel_safety(motor_name):
                self.function_motor_timers[motor_name] = {
                    "forward_time": 0.0,
                    "reverse_time": 0.0,
                    "last_update": now,
                    "forward_locked": False,
                    "reverse_locked": False
                }
        
        # Update existing timers - only for motors that were previously running
        for motor_name, timer_data in self.function_motor_timers.items():
            last_update = timer_data["last_update"]
            elapsed_ms = time.ticks_diff(now, last_update)
            elapsed_sec = elapsed_ms / 1000.0
            
            # Check if this motor was running in current_controls (from previous packet)
            previous_motor_data = self.current_controls.get("functionMotors", {}).get(motor_name)
            if previous_motor_data and elapsed_sec > 0:  # Motor was on and time has elapsed
                direction = previous_motor_data.get("dir", "fwd")
                
                # Store old times for halfway point detection
                old_forward_time = timer_data["forward_time"]
                old_reverse_time = timer_data["reverse_time"]
                
                # Only accumulate time if the direction is not locked
                if direction == "fwd" and not timer_data.get("forward_locked", False):
                    timer_data["forward_time"] += elapsed_sec
                    
                    # Check for halfway crossing to unlock reverse (ABSOLUTE requirement)
                    if self._motor_has_travel_safety(motor_name):
                        motor = self.motor_controller.motor_functions.get(motor_name)
                        if motor and hasattr(motor, 'travel_forward_limit'):
                            halfway_point = motor.travel_forward_limit / 2.0
                            # If we crossed halfway point, ALWAYS unlock reverse
                            if old_forward_time < halfway_point <= timer_data["forward_time"]:
                                if timer_data.get("reverse_locked", False):
                                    timer_data["reverse_locked"] = False
                                    print(f"HALFWAY: {motor_name} forward crossed halfway ({halfway_point:.1f}s) - unlocked reverse")
                                # Also reset reverse timer since we're moving away from reverse limit
                                timer_data["reverse_time"] = 0.0
                        
                        # Check if we hit the forward limit
                        if motor and timer_data["forward_time"] >= motor.travel_forward_limit:
                            timer_data["forward_locked"] = True
                            print(f"Forward travel limit reached for {motor_name}: {timer_data['forward_time']:.1f}s")
                            
                elif direction == "rev" and not timer_data.get("reverse_locked", False):
                    timer_data["reverse_time"] += elapsed_sec
                    
                    # Check for halfway crossing to unlock forward (ABSOLUTE requirement)
                    if self._motor_has_travel_safety(motor_name):
                        motor = self.motor_controller.motor_functions.get(motor_name)
                        if motor and hasattr(motor, 'travel_reverse_limit'):
                            halfway_point = motor.travel_reverse_limit / 2.0
                            # If we crossed halfway point, ALWAYS unlock forward
                            if old_reverse_time < halfway_point <= timer_data["reverse_time"]:
                                if timer_data.get("forward_locked", False):
                                    timer_data["forward_locked"] = False
                                    print(f"HALFWAY: {motor_name} reverse crossed halfway ({halfway_point:.1f}s) - unlocked forward")
                                # Also reset forward timer since we're moving away from forward limit
                                timer_data["forward_time"] = 0.0
                        
                        # Check if we hit the reverse limit
                        if motor and timer_data["reverse_time"] >= motor.travel_reverse_limit:
                            timer_data["reverse_locked"] = True
                            print(f"Reverse travel limit reached for {motor_name}: {timer_data['reverse_time']:.1f}s")
            
            timer_data["last_update"] = now
    
    def _motor_has_travel_safety(self, motor_name):
        """Check if a motor has travel safety enabled (cached for performance)"""
        # Check cache first
        if motor_name in self._travel_safety_cache:
            return self._travel_safety_cache[motor_name]
        
        # Compute and cache result
        has_safety = False
        if self.motor_controller and hasattr(self.motor_controller, 'motor_functions'):
            motor = self.motor_controller.motor_functions.get(motor_name)
            has_safety = motor and hasattr(motor, 'travel_safety_enabled') and motor.travel_safety_enabled
        
        self._travel_safety_cache[motor_name] = has_safety
        return has_safety
    
    def _check_function_motor_travel_safety(self, name, direction):
        """Check if function motor operation is allowed by travel safety"""
        timer_data = self.function_motor_timers.get(name)
        if not timer_data:
            return "allowed"  # No timer data yet, allow operation
        
        # Safety check: if both directions are locked, unlock both (should not happen but safety fallback)
        if timer_data.get("forward_locked", False) and timer_data.get("reverse_locked", False):
            print(f"WARNING: Both directions locked for {name} - unlocking both for safety")
            timer_data["forward_locked"] = False
            timer_data["reverse_locked"] = False
            # Reset timers to prevent immediate re-lock
            timer_data["forward_time"] = 0.0
            timer_data["reverse_time"] = 0.0
        
        # Get travel safety config from motor controller
        if self._motor_has_travel_safety(name):
            motor = self.motor_controller.motor_functions.get(name)
            if not motor:
                return "allowed"
            
            if direction == "fwd":
                # Check if forward is locked
                if timer_data.get("forward_locked", False):
                    return "locked"
                # Check if we've reached the limit
                if timer_data["forward_time"] >= motor.travel_forward_limit:
                    return "limit_reached"
                # If we're moving forward, unlock reverse direction (motor is moving away from reverse limit)
                if timer_data.get("reverse_locked", False):
                    timer_data["reverse_locked"] = False
                    print(f"Unlocked reverse direction for {name} (moving forward)")
                    
            elif direction == "rev":
                # Check if reverse is locked
                if timer_data.get("reverse_locked", False):
                    return "locked"
                # Check if we've reached the limit
                if timer_data["reverse_time"] >= motor.travel_reverse_limit:
                    return "limit_reached"
                # If we're moving reverse, unlock forward direction (motor is moving away from forward limit)
                if timer_data.get("forward_locked", False):
                    timer_data["forward_locked"] = False
                    print(f"Unlocked forward direction for {name} (moving reverse)")
        
        return "allowed"
    
    def get_travel_limited_motors(self):
        """Get list of travel-limited motors for status reporting"""
        limited = []
        for motor_name, timer_data in self.function_motor_timers.items():
            if timer_data.get("forward_locked"):
                limited.append(f"{motor_name}-forward")
            if timer_data.get("reverse_locked"):
                limited.append(f"{motor_name}-reverse")
        return limited
    
    def update_watchdog_timeout(self):
        """Update watchdog timeout from config"""
        self.watchdog_timeout_ms = get_config_value("motor_safety_timeout_ms", 400)

# Global control processor instance
_control_processor_instance = None

def get_control_processor():
    """Get the global control processor instance"""
    global _control_processor_instance
    return _control_processor_instance

def set_control_processor(instance):
    """Set the global control processor instance"""
    global _control_processor_instance
    _control_processor_instance = instance