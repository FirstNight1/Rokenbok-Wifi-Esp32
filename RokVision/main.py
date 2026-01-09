import time

time.sleep(2)  # allow USB enumeration before WiFi touches peripherals


import web.web_server
from RokCommon.variables.vars_store import init_config
from RokCommon.networking.wifi_manager import connect_to_wifi

import sys

if "/" not in sys.path:
    sys.path.append("/")

# Connect to Wifi
wlan = connect_to_wifi()

# Validation configuration and create/load defaults if needed
cfg = init_config()


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
