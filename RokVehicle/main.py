import time

time.sleep(2)  # allow USB enumeration before WiFi touches peripherals

import web.web_server
from variables.vars_store import load_config
from RokCommon.networking.wifi_manager import connect_to_wifi
from control.led_status import init_led_status, startup_blink, set_wifi_status

# Start UDP listener (non-blocking). Module auto-starts its thread on import.
import networking.udp_listener

cfg = load_config()

# Initialize LED and do startup blink
led_pin = cfg.get("ledPin", 9)
led_enabled = cfg.get("ledEnabled", True)
init_led_status(led_pin)

if led_enabled:
    startup_blink()
else:
    # If LED disabled, set override to keep it off
    from control.led_status import get_led_manager

    led_manager = get_led_manager()
    if led_manager:
        led_manager.set_override(True, False)

# Connect to Wifi
wlan = connect_to_wifi()

# Set LED pattern based on WiFi status and exit
if led_enabled:
    set_wifi_status()

# ---- Start async web server (non-blocking) ----
import _thread


def start_server_thread():
    _thread.start_new_thread(web.web_server.run, ())


start_server_thread()

print("System ready — async web server running in background.")
