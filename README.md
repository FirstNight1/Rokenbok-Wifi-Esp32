# Rokenbok-Wifi-Esp32

This project aims to replace the mainboards in Rokenbok vehicles with new microcontrollers to enable wifi connectivity for the vehicles, and control over wifi, bluetooth (limited to BLE controllers currently), and across the internet.  It also contains projects for implementing an FPV camera on each vehicle, as well as an overall system manager to orchestrate playing with and managing multiple vehicles.

## Release History:
This project has not yet been released as an official version, and is entirely a work in progress.

## Project Layout
RokCommon contains all of the basic shared functionality between the two main projects, RokVehicle, and RokVision.  For example, the wifi operation is the same between both projects, so would be in RokCommon.
RokVehicle is the specific adaptations for vehicle control, and is deployed to the controller responsible for motor and function control.
RokVision is the specific adaptations for FPV, and is deployed to the camera controller.

RokVision and RokVehicle both deploy to the root folder, so must contain a main.py and boot.py for each.  This also allows RokCommon to reference things like configuration files at the same path, regardless of vehicle type.  RokCommon is deployed as a directory under the root (/RokCommon/...), and is referenced that way by vehicle-specific files.

This approach ensures parity on functions and improvements between both projects, while simplifying updates and reducing drift between projects.

## Vehicle Conversion Notes
There are several conversion options with documented steps contained in the VehicleInfo folder.  This gives a brief overview of the various conversion options.
- Power Conversion: Adds a boost regulator to step up the input voltage to 5V
  - Allows using NiMh rechargeable batteries or similar while providing alkaline-like performance of the vehicle
  - Cost: $10-$15
  - Time: 15 minutes
  - Skill: Basic soldering
  - Compatibility: Compatible with Control conversion, and FPV conversion. NOT compatible with LiPo Power conversion.  Also compatible with stock control setup. 
  - Reversibility: Easily reversible to return to stock setup
- Control Conversion: Replaces the stock control board with a revised wifi-connected control setup
  - Allows for Wifi-based control of vehicle using a gamepad.  Hardware includes a controller, motor drivers, and supporting bits.
  - Cost: $20
  - Time: 1 hour
  - Skill: Intermediate soldering
  - Compatibility: Compatible with all other conversions.  Power conversion is not required, but can improve performance.
  - Reversibility: Not easily reversible to return to stock setup, but it is possible.
- FPV Conversion: Adds a small First Person View camera to provide a front view from the vehicle itself
  - Allows for a low/medium quality stream of the vehicle-mounted camera over Wifi.
  - Cost: $20
  - Time: 15 minutes
  - Skill: Basic soldering
  - Compatibility: Compatible with all other conversions.  Requires Power conversion to be reliable.  Can be used "standalone" (without control conversion) as well, though power conversion is still recommended.
  - Reversibility: Not applicable.  Potentially destructive in requiring holes to be drilled in the vehicle for wiring and/or the camera.
- Power Conversion - LiPo: Changes the battery to LiPo/LiIon and adds a charger and 5V regulator
  - WARNING: This is working with LiPo/LiIon batteries which are inherently dangerous.  If you don't know what you are doing, stick with the basic power conversion and rechargeable NiMh AA cells.
  - Replaces the 3xAA battery setup on board with a LiPo/LiIon pouch cell, while maintaining or improving on alkaline-like performance of the vehicle.  Charging is accomplished onboard by TBD
  - Cost: $20
  - Time: 30 minutes
  - Skill: Basic soldering
  - Compatibility: Compatible with Control conversion, and FPV conversion.  NOT compatible with basic Power conversion.
  - Reversibility: Not directly reversible due to physical modifications to battery bay and external charging input, however enough of the AA holders can be left for the vehicle to return to AA batteries if necessary.
- Power Conversion - Qi / Charging Input: Adds a specialty external charging input for a LiPo/LiIon battery via Qi, magnetic charger, and possibly other methods.
  - Available only on some vehicles, provides suggestions for Qi-based or other external charging connections for the vehicle
  - Cost: Varies
  - Time: 15 minutes
  - Skill: Basic soldering
  - Compatibility: Requires Power Conversion - LiPo.  Compatible with all other conversions.
  - Reversibility: Not applicable.  Potentially destructive in requiring holes to be made in the vehicle for wiring/connectors.


### LED Status Indicators (RokVehicle)
If the vehicle is equipped with LEDs (or the remote key slot is wired for the remote key LED), the lights will indicate the vehicle status and it's wifi connection:
- **Blinking on/off**: Startup or attempting to connect to WiFi
- **Solid on**: Successfully connected to WiFi (STA mode) 
- **Blinking bright/dim for 10 seconds, then solid**: Access Point (AP) mode active


# TODO List (Project-wide)

- [ ] Remove all debug logging and print statements from all code (production cleanup)
- [ ] Refactor and clean up every class for clarity and maintainability - suggest Claude Sonnet 4 to clean up GPT garbage.
- [ ] Check every web page and Python file for syntax issues and errors
- [ ] Fix: Crashes in the web server cause the REPL to hang; ensure graceful error handling and recovery
- [ ] Fix: Nothing restarts gracefully after a crash; implement robust restart logic
- [ ] Fix: WiFi retry logic—if WiFi fails the first time, subsequent retries immediately fail with 'WiFi Internal Error'; ensure retries are meaningful
- [ ] Add setting a password to AP mode rather than always using 1234567890
- [ ] Add a Readme.md in RokVehicle on flashing MicroPython and this program onto the board
- [ ] Add documentation in this Readme.md on the Play page, using gamepads, assigning control methodology and buttons, using axis controllers,
- [ ] Implement Play page FPV items
- [ ] Implement wifi scanning
- [ ] Implement direct bluetooth controller usage (BLE only)
- [ ] Test controller mapping and functionality on Play page
- [ ] FPV conversion instructions and setup
- [ ] FPV programming
- [ ] Test FPV stream integration locally on play page
- [ ] Play server instructions and setup
- [ ] FPV controls to wake and shut down the board/stream, and rotate the camera orientation 90deg in case of using a battery pack sideways
- [ ] Bluetooth gamepads directly
- [ ] Test with a true dpad gamepad, not a dpad-axis gamepad.
- [ ] Test with a two-stick gamepad (with dpad also)
- [ ] Move common components (web assets, web system, wifi system, configuration system, etc.) to shared/common folder, to remove repeated code.  RokVehicle and RokVision would then only have specific behavior to that.

'https://github.com/cnadler86/micropython-camera-API/releases/download/v0.6.1/mpy_cam-v1.27.0-ESP32_GENERIC_S3-SPIRAM_OCT.zip' -OutFile 'ESP32S3_camera_firmware.zip'"