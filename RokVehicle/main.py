import time
time.sleep(2)    # allow USB enumeration before WiFi touches peripherals

import web.web_server
from variables.vars_store import load_config
from networking.wifi_manager import connect_to_wifi, start_ap_mode

# Start UDP listener (non-blocking). Module auto-starts its thread on import.
import networking.udp_listener

cfg = load_config()

# Try STA mode first if configured
wlan = connect_to_wifi()

# If failed, go AP mode
if not wlan or not wlan.isconnected():
    print("Starting AP mode...")
    start_ap_mode(cfg["vehicleTag"])
else:
    print("Connected in STA mode.")

# ---- Start async web server (non-blocking) ----
import _thread

def start_server_thread():
    _thread.start_new_thread(web.web_server.run, ())

start_server_thread()

print("System ready — async web server running in background.")
