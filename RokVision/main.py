import time

time.sleep(2)  # allow USB enumeration before WiFi touches peripherals


import web.web_server
from variables.vars_store import load_config
from networking.wifi_manager import connect_to_wifi, start_ap_mode

import sys

if "/" not in sys.path:
    sys.path.append("/")
cfg = load_config()

# Try STA mode first if configured
wlan = connect_to_wifi()

# If failed, go AP mode
if not wlan or not wlan.isconnected():
    print("Starting AP mode...")
    start_ap_mode(cfg.get("vehicleTag", "RokVision"))
else:
    print("Connected in STA mode.")

# ---- Run both web server and camera stream in single asyncio event loop ----
import uasyncio as asyncio
from cam.camera_stream import start_camera_stream_async
import web.web_server


async def main():
    """Main async function to run both services concurrently"""
    try:
        print("Starting web server and camera stream...")

        # Start web server first (it's more critical)
        print("1. Starting web server...")
        web_task = asyncio.create_task(web.web_server.start_web_server())

        # Give web server a moment to start
        await asyncio.sleep(2)

        # Then start camera stream
        print("2. Starting camera stream...")
        camera_task = asyncio.create_task(start_camera_stream_async(cfg))

        # Give camera stream a moment to initialize
        await asyncio.sleep(2)

        print("System ready — web server and camera stream running concurrently.")

        # Wait for both tasks (they should run indefinitely)
        await asyncio.gather(web_task, camera_task, return_exceptions=True)

    except Exception as e:
        print(f"System error: {e}")
        import sys

        sys.print_exception(e)


# Run the main async function
try:
    asyncio.run(main())
except Exception as e:
    print(f"Failed to start system: {e}")
    import sys

    sys.print_exception(e)
