# RokVehicle Readme

## Checking for PSRAM and Flashing MicroPython Firmware

### 1. Does your board have PSRAM?

| Board Name | PSRAM? | Official Specs Link |
|------------|--------|---------------------|
| Seeed Studio XIAO ESP32-C3 | ❌ No | [Specs](https://wiki.seeedstudio.com/XIAO_ESP32C3_Getting_Started/) |
| Seeed Studio XIAO ESP32-S3 | ❌ No | [Specs](https://wiki.seeedstudio.com/SeeedStudio_XIAO_Series_Introduction/) |
| Seeed Studio XIAO ESP32-S3 Sense | ✅ Yes (8MB) | [Specs](https://wiki.seeedstudio.com/SeeedStudio_XIAO_Series_Introduction/) |
| ESP32 WROVER modules | ✅ Yes | [Specs](https://www.espressif.com/en/products/modules/esp32/wrover) |

If you have a XIAO ESP32-S3 Sense, you have 8MB PSRAM. The regular XIAO ESP32-S3 and ESP32-C3 do **not** have PSRAM.

### 2. Download the correct MicroPython firmware

- For most ESP32 boards (including XIAO ESP32-S3 Sense):
  - **With PSRAM:** Download the latest "SPIRAM" (PSRAM) firmware from the [official MicroPython ESP32 download page](https://micropython.org/download/esp32/). Example: `ESP32_GENERIC-SPIRAM-*.bin`.
  - **Without PSRAM:** Download the regular `ESP32_GENERIC-*.bin` firmware from the same page.

### 3. Flashing the firmware (step-by-step)

**A. Install esptool:**
1. Download and install [Python](https://www.python.org/downloads/) if you don't have it.
2. Open Command Prompt (Windows) and run:
	```
	pip install esptool
	```

**B. Put your board in bootloader mode:**
1. Unplug the board from USB.
2. Hold the BOOT button (if present), plug in USB, then release the button.

**C. Erase the flash (recommended):**
1. Find your board's COM port (e.g. COM10 in Device Manager).
2. Run:
	```
	esptool.py --port COM10 erase_flash
	```

**D. Flash the firmware:**
1. Download the `.bin` file for your board (see above).
2. Run:
	```
	esptool.py --port COM10 --baud 460800 write_flash 0x1000 FIRMWARE_FILE.bin
	```
	Replace `FIRMWARE_FILE.bin` with your downloaded file name.

**E. First boot:**
1. Unplug and replug the board. It should now run MicroPython.
2. Use [mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html) or a serial terminal to connect.

**Troubleshooting:**
- If flashing fails, try a lower baud rate (remove `--baud 460800`).
- If you get stuck, repeat the erase and flash steps.

**More info:**
- [MicroPython ESP32 Download Page](https://micropython.org/download/esp32/)
- [Seeed Studio XIAO Series Comparison](https://wiki.seeedstudio.com/SeeedStudio_XIAO_Series_Introduction/)