import time

time.sleep(3)  # Extended delay for ESP32-S3 peripheral initialization

import web.web_server
from RokCommon.variables.vars_store import init_config, get_config_value
from RokCommon.networking.wifi_manager import connect_to_wifi
from RokCommon.control.network_led import init_network_led
from control.vehicle_led import init_vehicle_led


# Initialize configuration first
cfg = init_config()

led_pin = get_config_value("ledPin", 9)
led_enabled = get_config_value("ledEnabled", True)
busy_led_enabled = get_config_value("busyLedEnabled", False)
busy_led_pin = get_config_value("busyLedPin", -1)

# Check for shared LED mode
shared_mode = (led_enabled and busy_led_enabled and 
               led_pin != -1 and busy_led_pin != -1 and 
               led_pin == busy_led_pin)

# Initialize network status LED (common)
network_led = init_network_led(led_pin, shared_mode)

# Initialize vehicle LED manager (busy LED + vehicle functions)
# Skip busy LED initialization if in shared mode
vehicle_led = init_vehicle_led(busy_led_pin if (busy_led_enabled and not shared_mode) else None)

if shared_mode:
    pass  # Shared LED mode - no separate status message needed


if led_enabled:
    # Start network LED startup sequence
    network_led.start_startup_blink()
else:
    # If LED disabled, set override to keep both off
    network_led.set_override(True, False)

if busy_led_enabled and vehicle_led:
    # Start busy LED monitoring
    vehicle_led.start_busy_monitoring()

# Connect to Wifi
wlan = connect_to_wifi()

# Set LED pattern based on WiFi status
if led_enabled:
    # Update network status LED
    network_led.set_wifi_status()

# ---- Start async web server (async-only, no threading) ----
print("Starting web server in async mode...")

# Run web server in main async loop instead of separate thread
web.web_server.run()

print("System ready — async server running.")
