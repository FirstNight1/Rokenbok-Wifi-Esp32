import time
import sys

# Extended delay for ESP32-S3 peripheral initialization  
time.sleep(3)

import web.web_server
from RokCommon.variables.vars_store import init_config, get_config_value
from RokCommon.networking.wifi_manager import connect_to_wifi
from RokCommon.control.network_led import init_network_led

if "/" not in sys.path:
    sys.path.append("/")

# Validation configuration and create/load defaults if needed
cfg = init_config()

# Initialize network status LED (default pin 9, but can be configured)
led_pin = get_config_value("ledPin", 9)
led_enabled = get_config_value("ledEnabled", True)

network_led = init_network_led(led_pin)

if led_enabled:
    # Start network LED startup sequence
    network_led.start_startup_blink()
else:
    # If LED disabled, set override to keep it off
    network_led.set_override(True, False)

# Connect to Wifi
wlan = connect_to_wifi()

# Set network LED pattern based on WiFi status
if led_enabled:
    network_led.set_wifi_status()

# ---- Run both web server and camera stream in single asyncio event loop ----
import uasyncio as asyncio
from cam.camera_stream import start_stream


async def main():
    """Main async function to run both services concurrently"""
    try:
        # Start web server first (it's more critical)
        web_server = await web.web_server.start_web_server()

        # Give web server a moment to start
        await asyncio.sleep(1)

        # Then start camera stream
        camera_started = await start_stream()
        if not camera_started:
            print("Warning: Camera stream failed to start")
        else:
            print("Camera stream started successfully")

        # Give camera stream a moment to initialize
        await asyncio.sleep(1)

        print("System ready — camera stream running concurrently.")

        # Keep both running - just wait indefinitely
        # Both servers will run until the system is shut down
        while True:
            await asyncio.sleep(60)  # Check every minute

    except Exception as e:
        print(f"System error: {e}")
        import sys
        sys.print_exception(e)


# Run async main directly (no threading)
print("Starting system in async mode...")
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("\nSystem shutdown requested")
except Exception as e:
    print(f"Failed to start system: {e}")
    import sys
    sys.print_exception(e)
