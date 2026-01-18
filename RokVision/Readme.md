# 📹 RokVision - FPV Camera System for ESP32-S3

RokVision provides wireless FPV (First Person View) camera streaming for Rokenbok vehicles using the SeeedStudio XIAO ESP32-S3 Sense module. It supports both **OV2640** and **OV3660** camera sensors.

## 🎯 Features

- **📡 Wireless MJPEG streaming** - View directly in any web browser
- **🔍 Works with all XIAO ESP32S3 Sense Cameras** - Works with both OV2640 and OV3660 sensors
- **🌐 WiFi connectivity** - AP mode or connect to your home network
- **⚙️ Web-based configuration** - Easy setup through browser interface
- **📱 Cross-platform viewing** - Compatible with phones, tablets, computers
- **🚀 High performance** - Optimized for real-time streaming

## 📦 Hardware Requirements

### Required Components
- **SeeedStudio XIAO ESP32-S3 Sense** (with camera module)
  - Supports both OV2640 and OV3660 camera variants
  - Must have PSRAM (8MB recommended)
- **USB-C cable** for programming and power
- **Power source** for mobile use (battery pack, vehicle power, etc.)
- **(Optional) OV2640 camera separately - see note** for better FPV frame rates

### Supported Cameras
- **OV2640** - 2MP camera (older boards) - I2C address 0x30
- **OV3660** - 3MP camera (newer boards) - I2C address 0x3C

## Camera Sensor Note
The Seeed XIAO ESP32-S3 Sense mostly ships now with the OV3660 camera, which is a higher resolution camera, but lacks a native JPEG encoder in the hardware.  Both cameras get their best FPS (balanced with resolution) at CIF or QVGA resolution, which is about 320x240.  The OV3660 just by limitation of the camera hardware and micropython gets about 11 FPS.  The OV2640 gets about 25 FPS at the same resolution. Unfortunately, increasing to VGA resolution drops framerates to about 6FPS on both boards. 

For that reason, I suggest purchasing the OV2640 separately, they're about $5 each. They are a direct replacement for the OV3660, you just need to lift the black lever to disengage the ribbon connector, and insert the ribbon connector for the new camera, adjust the camera type on the admin page, and you're good to go.

### FPV Future
Rewriting the FPV into C or using another streaming methodology might be able to increase this, but 25 FPS at QVGA is pretty reasonable to drive with.  A future TODO is to add taking full-resolution snapshots on-demand, so say you are stuck somewhere or want to see something better, you can click a camera on the interface and get a full-resolution picture back, then it'll go back to low resolution streaming.  This determination was made that the area camera will stream in 1080p/4k, so the FPV camera being lower resolution is fine just to get a more frontal view of your vehicle when it is obscured from the area camera or in a tight place.

## 🚀 Quick Start Guide

### Step 1: Install Prerequisites

**Windows:**
1. Download and install **Python 3.8+** from [python.org](https://python.org)
2. Open Command Prompt or PowerShell as Administrator
3. Install required tools:
   ```cmd
   pip install mpremote esptool
   ```

**macOS/Linux:**
```bash
pip3 install mpremote esptool
```

### Step 2: Download Compatible Firmware

RokVision requires special MicroPython firmware with camera API support:

1. **Download firmware:**
   - Go to: [micropython-camera-API releases](https://github.com/cnadler86/micropython-camera-API/releases)
   - Download: `mpy_cam-v1.27.0-ESP32_GENERIC_S3-SPIRAM_OCT.zip`
   - Extract the `firmware.bin` file

2. **Alternative download (direct link):**
   ```cmd
   curl -L -o ESP32S3_camera_firmware.zip "https://github.com/cnadler86/micropython-camera-API/releases/download/v0.6.1/mpy_cam-v1.27.0-ESP32_GENERIC_S3-SPIRAM_OCT.zip"
   ```

### Step 3: Connect Your XIAO ESP32-S3

1. **Connect USB-C cable** to your XIAO ESP32-S3 Sense
2. **Put device in bootloader mode:**
   - Hold the **BOOT** button
   - Press and release **RESET** button
   - Release **BOOT** button
   - Device should appear as a new COM port

3. **Find COM port:**
   
   **Windows:**
   ```cmd
   python -m esptool port_list
   ```
   Look for `Silicon Labs CP210x` or similar

   **macOS/Linux:**
   ```bash
   ls /dev/tty.usb* /dev/ttyUSB*
   ```

### Step 4: Flash Camera-Compatible Firmware

⚠️ **Important:** This will erase existing data on the device.

```cmd
# Replace COM13 with your actual COM port
# Replace path with actual path to firmware.bin

python -m esptool --port COM13 erase_flash
python -m esptool --chip esp32s3 --port COM13 write_flash -z 0x0 firmware.bin
```

**Expected output:**
```
Connected to ESP32-S3 on COM13:
Flash memory erased successfully
Wrote 1948288 bytes (1234667 compressed) at 0x00000000
Hash of data verified.
```

### Step 5: Download and Install RokVision

1. **Download RokVision project:**
   ```cmd
   git clone https://github.com/FirstNight1/Rokenbok-Wifi-Esp32.git
   cd Rokenbok-Wifi-Esp32/RokVision
   ```

2. **Upload RokVision files to device:**
   ```cmd
   # Replace COM13 with your actual COM port
   python -m mpremote connect COM13 cp -r . :/
   python -m mpremote connect COM13 reset
   ```

### Step 6: First Time Setup

1. **Wait for startup** (about 10-15 seconds after reset)

2. **Connect to RokVision AP:**
   - Look for WiFi network: `FPV-RokVision-XXXXXX`
   - Password: `1234567890`

3. **Open web interface:**
   - Go to: `http://192.168.4.1` in your browser
   - You should see the RokVision home page

4. **Configure settings:**
   - Click **Admin** to set vehicle type, name, etc.
   - Click **WiFi** to connect to your home network (optional)
   - Click **Testing** to verify camera function

## 🎮 Using RokVision

### Viewing Camera Stream

**In AP mode:**
- Direct URL: `http://192.168.4.1:8081/stream`

**On home network:**
- Find device IP on your router
- URL: `http://<device-ip>:8081/stream`

### Web Interface Pages

- **🏠 Home** - System status and quick links
- **⚙️ Admin** - Device configuration  
- **📡 WiFi** - Network settings
- **🧪 Testing** - Camera and system tests

### Embedding in Other Applications

The MJPEG stream can be embedded in any web page:
```html
<img src="http://192.168.4.1:8081/stream" alt="FPV Camera Stream">
```

## 🔧 Advanced Configuration

### Camera Settings

Available in Admin panel:
- **Frame Size:** QQVGA, QVGA, CIF, VGA, SVGA
- **Quality:** 1-100 (higher = better quality, larger files)
- **Contrast, Brightness, Saturation:** -2 to +2
- **Flip/Mirror:** For mounting orientation

### Performance Tuning

**For better streaming performance:**
- Use **QVGA (320x240)** for real-time streaming
- Set **Quality to 80-85** for best size/quality balance
- Ensure strong WiFi signal
- Use 5GHz WiFi when possible

**For still image capture:**
- Can use up to **SVGA (800x600)** on OV3660
- Increase **Quality to 90+** for photos

### Network Configuration

**Static IP Setup:**
1. Go to WiFi page
2. Uncheck "Use DHCP" 
3. Enter IP, Subnet, Gateway, DNS
4. Save and reboot

**AP Mode Customization:**
1. Go to Admin page
2. Change "Vehicle Tag" to customize AP name
3. AP name becomes: `FPV-<VehicleType>-<Tag>`

## 🛠️ Troubleshooting

### Camera Not Working

**❌ "Camera not supported" errors:**
- ✅ **Solution:** Flash the correct camera firmware (Step 4)
- The default MicroPython firmware doesn't support cameras

**❌ "Camera detection failed":**
- ✅ Check camera cable connection
- ✅ Try power cycling the device  
- ✅ Verify camera is properly seated

**❌ Stream shows "No image" or black screen:**
- ✅ Check camera LED is on (small light near camera)
- ✅ Try different frame size in Admin panel
- ✅ Check if lens cap is removed (if applicable)

### Connection Issues

**❌ Can't find RokVision WiFi network:**
- ✅ Wait 30 seconds after reset for AP to start
- ✅ Device may have connected to configured WiFi instead
- ✅ Try 3 rapid resets to force AP mode

**❌ Can't access web interface:**
- ✅ Ensure connected to correct WiFi network
- ✅ Try `http://192.168.4.1` (AP mode) or device IP
- ✅ Disable VPN if active

**❌ Poor video quality/lag:**
- ✅ Reduce frame size (try QVGA)
- ✅ Lower quality setting (try 75)
- ✅ Move closer to WiFi router
- ✅ Check for interference from other devices

### Firmware Issues

**❌ Device not recognized:**
- ✅ Install CP210x drivers from Silicon Labs
- ✅ Try different USB cable
- ✅ Use USB 2.0 port (some USB 3.0 ports cause issues)

**❌ Upload fails:**
- ✅ Ensure device is in bootloader mode (hold BOOT, press RESET)
- ✅ Try slower upload speed: `--baud 115200`
- ✅ Check cable and port

### Getting Help

**System Information:**
```cmd
python -m mpremote connect COM13 exec "import os; print('\\n'.join(os.uname()))"
```

**Check logs:**
```cmd  
python -m mpremote connect COM13 repl
```
Look for error messages during startup.

## 📡 Technical Details

### Camera Specifications

| Feature | OV2640 | OV3660 |
|---------|---------|---------|
| Resolution | 2MP (1600x1200) | 3MP (2048x1536) |
| I2C Address | 0x30 | 0x3C |
| Clock Speed | 10MHz | 20MHz |
| Recommended Frame Size | QVGA-CIF | QVGA-SVGA |

### Network Details

**AP Mode:**
- SSID: `FPV-<VehicleType>-<Tag>`
- Password: `1234567890` (configurable in future)
- IP Range: 192.168.4.1-192.168.4.254
- Device IP: 192.168.4.1

**Stream Details:**
- Protocol: HTTP MJPEG
- Port: 8081 (configurable)
- Format: multipart/x-mixed-replace
- Browser compatible: Chrome, Firefox, Safari, Edge

### Pin Configuration (XIAO ESP32-S3)

| Function | Pin | Description |
|----------|-----|-------------|
| Data 0-7 | 15,17,18,16,14,12,11,48 | Camera data bus |
| VSYNC | 38 | Vertical sync |
| HREF | 47 | Horizontal reference |
| PCLK | 13 | Pixel clock |
| XCLK | 10 | External clock |
| SDA | 40 | I2C data |
| SCL | 39 | I2C clock |

## 📚 Additional Resources

- **Project Repository:** [Rokenbok-Wifi-Esp32](https://github.com/FirstNight1/Rokenbok-Wifi-Esp32)
- **Camera Firmware:** [micropython-camera-API](https://github.com/cnadler86/micropython-camera-API)
- **MicroPython Docs:** [micropython.org](https://micropython.org)
- **XIAO ESP32-S3 Guide:** [Seeed Studio Wiki](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/)

## 🤝 Contributing

Found a bug or want to contribute? Please open an issue or pull request on GitHub!

---

*RokVision - Part of the Rokenbok-Wifi-Esp32 project*