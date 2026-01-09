# Control Conversion

## Converts vehicle control to ESP32-based control and motor driver system

### Allows for vehicle control over Wifi using a host device (phone, laptop, etc.) and gamepad.

## Prerequisites:
This modification can be performed alone, and works fine with the stock battery setup and either Alkalines or NiMh rechargeables.  It can also be done in conjunction with either of the power conversions and/or with the FPV conversion as well.  It can be accomplished without opening up the vehicle beyond removing the drive base, though the tightness of some wires may make that more difficult in certain cases.  This modification is not easily reversible, and is not compatible with either the Rokenbok RC or RokStar systems.

### Hardware Needed
1x Seeed Studio XIAO ESP32-S3 (C3, C6, and other variants or similar boards from other manufacturers also likely work.  This project was written and tested specifically with the XIAO S3 variant, which includes PSRAM)  Cost is about $7-$10 per board.
1x heatsink - should be included with ESP32-S3.  Not strictly necessary as these don't get that hot, but good safety.
2x DRV8833 breakout motor driver boards (generic, $1-2 each)

220ohm 1/4 watt resistors, if the vehicle has LEDs (optional)
1x power switch (optional)
Wire - 24ga, 30ga(optional) mounting tape or glue, solder, and other miscellanious electronics bits may be required
(This project requires mid-level soldering skills)

### Difficulty
WARNING: This conversion is not designed to be easily reversible.  You will need soldering skills, and a willingness to take your vehicle apart, including potentially damaging it irreparably.  Do not expect to be able to go back to the stock configuration/setup if something goes wrong.  Theoretically all the stock wiring is still there, and/or you could run new wire to the stock motors and vehicle keyway, and attach those back to the stock control board.

If you intend to ever reverse this modification, I would suggest taking thorough pictures of the existing wiring connections on the controller board (pictures will be included as possible from my vehicles in the Vehicle Info folder as well), and carefully de-solder the motor, LED, and key wires from the board, that way they can be re-attached.  For ease of reversal, it may be worthwhile to utilize screw terminal blocks on your breakout and control boards, which will minimize re-soldering needed of the existing small vehicle wires.

## Conversion Directions
### Disassembly Required
1. Follow the directions for your specific vehicle type to remove the drive base.  Typically this will only involve removing two screws from the rear of the vehicle to detach the drive base.  BNe careful of the existing wiring.
2. Desolder the wires from the stock control board, or cut them as close as possible to the board, leaving the maximum amount of wire to connect to the new control system.  Remove the stock control board.  If your vehicle has multiple wires of the same color and gauge, you may wish to label them as to their function.

### Preparation
Instructions for flashing the firmware and software are included in the Readme.md in RokVehicle, and are specific to RokVehicle.\
1. Flash the ESP32-S3 (or variant) with the appropriate Micropython firmware, including the PSRAM option if your board has PSRAM.  Seeed Studio XIAO S3 boards all have PSRAM.  PSRAM is used to enable OTA updates (updating the software without physical access to the board and it's usb port).
2. Program the ESP32-S3 with the latest RoKVehicle release.

### Control Conversion
1. A general wiring diagram / schematic is included below, and shows the connections for a 4-motor vehicle.  To use this in conjunction with a power conversion, you will simply change to connect to the 5V pin of the power board rather than the batteries, and omit the switch (it will have been installed with the power conversion if desired).
2. Vehicles with non-motor functions like additional lights or sounds will typically use pins D8 and D9, instructions for hooking up those functions will be found in the vehicle specific documentation.
3. If performing in conjunction with any other conversion(s), I suggest gathering the main boards for all conversions, and determining the placement for all of them prior to beginning.  It can be helpful to be able to access the USB-C port on the ESP32 controller.  They do make low profile and right angle cables as well if necessary, basically just don't put the usb port up against a wall in the vehicle.  The vehicle specific documentation may have some suggestions on this for vehicles that have space outside the drive base to put boards.
4. The basic theory is you will connect power and ground from the battery or power conversion to the controller board and one or two motor driver boards (most vehicles will need two motor driver boards, but may only drive 3 total motors.  In this case one channel on one controller will simply not be populated with control or output wires.)
  - Next, you will need to make connections between the controller and the motor drivers, consisting of up to eight total control signal wires, depending on the number of motors on the given vehicle.
  - Third, you will connect the existing vehicle motor wiring to the motor drivers, consisting of two input wires per motor, and connecting any now-unconnected casing grounds to other motor casings, or the battery ground.
  - Lastly, you will connect any LEDs or accessories/non-motor functions that may be on the vehicle to remaining controller pins.

5.  After determining placement of the boards needed, determine how you will connect the boards: soldering, with terminals, etc.  The red, black, yellow, and white wires on the diagram (power and motor wires) need to be 24ga.  The blue wires are signals and can be done in 30ga if desired, or still in 24ga.  The LED wires despite being blue and black can also be 30ga for both, because I expect to use the wires already attached to the lights or radio socket.  But, if you're running new wire, those can also use 30ga just fine.
  - After doing 3 vehicles and not being completely happy with any of them, here are a couple suggestions.
  - Just do 28ga wire wrap for all connections between boards, including +5V and GND from a power board if applicable.  It can handle it, especially if you do separate wire runs to each motor controller and ESP32 from the 5V and GND pins.
  - Don't put headers on pins that get external connections or are unused.  
    - Motor drivers, put a header on the IN and power half, but don't put anything on the output half.
    - ESP32 gets pins on D0-D7, D8 if desired, and D9 if desired.  Solder a resistor for LEDs in D10 (leave more free if the vehicle has non-motor functions and will need a speaker or more LEDs hooked up).  Headers on VUSB and GND.
    - Power board (if using) gets headers on all pins except Bat and one GND terminal.  Change to pin-backed swtich rather than soldering.
  - Still solder and run a 24ga to the battery + and - for the power board (if using). 
  - Option 2 is do a combination of 30ga wire wrap for signals, and soldering for 24ga with a bundle for +5V and GND.
  - Option 3 (untested yet) is to use a protoboard to mount everything instead and make connections on the protoboard for all internal connections, then solder all external connections.
  - Directions for Option 2 (partly also applicable to Option 1):
    - Prep: Solder 0.1 header pins on D0-D6, and D7 on vehicles with 4 motors on the ESP32, with the pins up through the back of the board (so a heatsink on the back can stick upwards).  Solder header pins on IN1/IN2, IN3/IN4 on each driver motor board, sticking above the top of the board with components on it.
    - Prep: Solder 24ga +5V wires to the ESP32 VUSB and motor driver Vin (and +5V if applicable), have the wires about 3" long and leave the ends loose to bundle later.  Do the same for GND on the ESP32, motor drivers, and power board if applicable.  Follow the direction of the headers (top/component side on motor drivers and power board, non-chip side on ESP32)
    - Prep: Solder 220ohm resistors into holes as appropriate for vehicle (most vehicles will have one)
    - Solder the drive motor wires to motor driver 1.  Mount motor driver 1.
    - Plug in an antenna to the ESP32, and connect/solder any remaining 24ga wires (speaker, functions, etc.) and mount it, using a plugged in USB cable as a guide for angling.  After mounting, add a single heatsink as low as possible over the chip die.
    - Solder wires for the EN, LB, and GND on the power board, leaving enough to reach a switch, if being used.  Solder wires for Bat and GND on the power board, leaving enough to reach the battery + and - terminals.  Mount the power board.
    - Position motor driver 2, but do not mount it.
    - Complete wiring of power board, except ground and +5V pigtails hanging still.
    - Make wire wrap connections from D0-D3 to motor driver 1.
    - Start making connections from non-drive parts of vehicle, starting with motor driver 2 connections and mounting.
    - Continue with ESP32 connections to non-drive parts of vehicle, such as LEDs, speaker, etc.
    - Solder a +5V and GND wire to an FPV board, if using, and mount it in the vehicle shell.  Leave enough wire to reach down into the drive base.
    - Ensure all wires into drive base are connected except for +5V bundle, and GND bundle (including any motor casing grounds)
    - Twist, solder, and heat shrink +5V bundle and GND bundle
6. Solder the wiring between the boards following the next step before mounting them on the vehicle.  Or, solder/attach terminal blocks to the boards, then mount the boards to the vehicle in the desired configuration, then complete the wiring.
7. Complete the wiring connections as given on the wiring diagram.  NOTE: which motor is wired to which pair of pins is configurable in the software, in case the order of motors and wiring does not match exactly.  The critical thing is each motor and pair of wires for it is in one of the following pin combinations: D0/D1, D2/D3, D4/D5, D6/D7, D8/D9. LEDs can be in any free pin not utilized by the motors, speakers and other functions may have different requirements, so refer to those vehicle's pages for more info.
  * 24ga wire between battery negative, GND on motor driver 1, GND on motor driver 2, GND on the ESP32, any loose gray motor casing wires, and LED negatives.
  * 24ga wire between battery positive OR 5V power regulator output, Vin on motor driver 1, Vin on motor driver 2, and VUSB on ESP32.
  * 24ga wire (existing) from drive motor left to out 1 and 2 on motor driver 1.
  * 24ga wire (existing) from drive motor right to out 3 and 4 on motor driver 1.
  * 30ga wire from D0, D1, D2, and D3 on ESP32 to IN4, IN3, IN2, and IN1 on motor driver 1, respectively.
  * 24ga wire (existing) from function motor 1 (see vehicle specific documentation) to out 1 and 2 on motor driver 2.
  * If applicable, 24ga wire (existing) from function motor 2 to out 3 and 4 on motor driver 2.
  * 30ga wire from D4 and D5 to IN4 and IN3 on motor driver 2, respectively.
  * If applicable, 30ga wire from D6 and D7 to IN2 and IN1 on motor driver 2, respectively.
  * 30ga wire to 220ohm resistor to LED positives.

8. After completing the hardware modifications, it is important to verify all wiring connections prior to powering on the vehicle.  Take a minute and double check your wiring against the circuit diagrams, and ensure all connections make sense (i.e. you aren't shorting the battery leads together anywhere).
9. Hopefully you flashed the software onto the controller before you put it in the vehicle, otherwise dig up a usb-c cord (right angle ones are available and can be helpful if you glued yourself into a jam) and follow those instructions in the RokVehicle project now.

### Usage
1. On initial startup of a new vehicle, it will create a Wifi Access Point (AP) that looks like loader-XYZABC.  This network name is the tag for the vehicle, and consists of the vehicle type and it's unique tag.  The default vehicle type is loader, we'll update this shortly.  Connect a phone or computer to the access point.  The default password for the access point is 1234567890.  The vehicle should have an IP address of 192.168.4.1, and should assign your device an IP address of 192.168.4.2.
2. Open Chrome (or an internet browser) on the device, and navigate to http://192.168.4.1, which should load the home page for the vehicle, and show various information about the vehicle.
3. Navigate to the Admin page link in the header, which will take you to a page where you can configure the general settings for the vehicle.  Select the correct vehicle type from the list.  When you select a vehicle type from the list, it will update the tag prefix as well.  I suggest keeping the same vehicle tag, but you can also set a custom vehicle tag if desired, ensure it is unique for each vehicle.  You can also set a "friendly name" for the vehicle, useful to differentiate Power Sweeper 1 and Power Sweeper 2 if you have multiple, for example.  Click save to save your updates.  The change to the AP network name to match the new tag will NOT take effect until the vehicle is rebooted.  You can also set the pin you used for the LEDs here (note it will grey out pins used by the motors, so you may need to come back after you configure the motors to set the correct pin for the LEDs).
4. If you are going to use the AP to control the vehicle, go ahead and reboot it now by turning it off and on, or removing and replacing the batteries, and connect your device to the new AP.  If you plan to connect the vehicle to your home wifi and control it that way, then navigate to the wifi page and enter your wifi details.  By default, the vehicle will use DHCP to connect to this wifi network, though you can set a static IP on this page if needed.  In DHCP mode, you will need to use the tools available on your router, or other network scanning tools to locate the IP address of the vehicle.  I suggest either setting a static IP on the vehicle, or associating a designated IP to it via your router, if available (Setting it to a forced IP on the router also blocks the router from assigning that IP elsewhere, which prevents IP address conflicts.  If setting a static IP on the vehicle, try to use a portion of your subnet that is excluded from the DHCP range on your router).
  * When the vehicle boots up, it will attempt 5 times to connect to the wifi network, if configured.  If the vehicle is unable to connect to the network, it will "fall back" to AP mode, and you will see a network with the tag of the vehicle, just like in step 7.  You can use this to check and correct any errors in the wifi settings.  Or also works great if you travel with the vehicle and want to use it away from your configured network, it will quickly fall into AP mode and you can play with it that way.
NOTE: If you get stuck on a bad wifi network or set a bad static IP or similar, reboot the vehicle 3 times in rapid succession (less than 20 seconds between reboots), and it will force the vehicle into AP mode, so you can connect back and edit the wifi/IP settings.  Note that this will not clear your stored wifi network and credentials, so future reboots will still attempt to connect back to the configured network unless you make edits.
5. The vehicle should now be connected to your network, or you are using it in AP mode.  It's time to configure things for your specific vehicle hardware.  Go to the Motor Config page.  The browser should open a websocket to the vehicle (which emulates how a controller will control the vehicle), and then give a list of the motors present on the vehicle, and some configuration items for each: A motor port number (in case you wired your vehicle different from the schematic), a minimum power per motor (controlled on a scale from 1-65), and a reversed checkbox.  The reversed checkbox is used for drive or function motors if they rotate opposite the intended direction for "forward" and "reverse", for example it's easy to miss wiring the drive motors opposite each other so both go forward and reverse together, this will let you swap that.  Or if the sweeper is intaking balls on reverse rather than forward, etc.
  * Ensure the pinouts for each motor, which should be correct if you followed the schematic (left is motor 1, right is motor 2, etc.)  If these are incorrect, use the dropdowns to reassign the motor numbers, ensuring each motor is a unique motor number.  The pinouts for each motor are also listed for convenience.
  * Motor 1 is D0/D1, Motor 2 is D2/D3, Motor 3 is D4/D5, Motor 4 is D6/D7, Motor 5 is D8/D9.
  * Test each motor by pressing it's forward or reverse button.  The motor selected should run for 1 second and stop.  If the motor doesn't run at all, verify the motor is hooked up correctly, cross reference the motor driver output and input pins, and ensure the pins connected on the controller board match those on the motor config page.  If the motor tries to run but doesn't turn, up the power setting to 100% and try again.  If the motor still tries to turn but doesn't run, you likely have a bad motor connection, bad motor, stuck or broken gearing, or similar.  In that case, you're likely going to have to resort to opening up the vehicle and cleaning out the area of the motor in question.  This may also be affected by your power source, the controller can run at very low voltages compared to what the motors need, but the motors are powered directly by the voltage from the battery (barring using one of the power mods described below).  Try fresh batteries, or if using NiMH, try alkalines since they're higher voltage, just in case.
  * Once you have confirmed all motors run and thus are associated to the correct motor number/pinout, it's time to configure each one for your specific vehicle, power source, and motor condition.
  * There are two motor types defined on each vehicle. First are "axis" motors, which are always the left and right drive motors, and/or may include certain other motors on some vehicles.  This designation indicates these motors can be controlled by a gamepad axis (joysticks, axis buttons like Z/L/R on some gamepads, etc.).  The second motor type is "function" motors, which are simple on/off control, usually including like the bed raise on trucks, intake on the street sweeper, and similar.
  * Axis motors have a "Minimum Power" setting.  This will be different based on your source of power, motor age, gearing cleanliness, and other factors, and is used to provide a lower bound for axis-based input for those motors.  The available minimums are 1-65, with a default of 40.  To test these, change the power field to 100%, and click forward or reverse.  Adjust the minimum power until the motor runs at a slow speed under load (with the vehicle on its wheelbase for example driving), but doesn't stall out.  On NiMH batteries which are lower voltage, this will likely be a slightly higher number. Alkalines or running with a voltage converter can provide more motor power/speed, so the minimum power number will likely be a little lower, allowing a greater range of control.
    * You may also find you need to re-adjust this setting to compensate for as batteries deplete, and you should keep the higher setting you may get this way.  The goal is to have the minimum power keep the motor turning in all situations - dying batteries, vehicle is going up a ramp, anything "worst case" - while still keeping some range of speed available for axis control.  If you find you are stalling a motor frequently at low input, increase this minimum power by a few until you aren't stalling it, and then keep that higher minimum power setting (don't adjust it back down next time).  
  * Next is to adjust the motor default forward direction.  When you command a motor "forward" it should drive the vehicle forward, or drive the bed in whatever you consider "forward" (raise the bed is the default forward), etc.  If you hooked up a motor backwards, so clicking "forward" is driving it backwards, simply click the toggle reversed button, and it'll flip that motor for you, so that forward is forward.
12. You should now have a fully configured vehicle you are ready to play with! Go to the Play screen via the header, or the Play Now button on the home screen, and you should be able to connect a controller to your device and control the vehicle!  The Play page is explained in more detail later on, as is the RokServer multiplayer interface.

### Notes on Controllers
The play page was originally written to support direct connection of a bluetooth controller to the vehicle, for easy local play once set up.  However, the ESP32-S3 and Micropython only support BLE HID controllers, which are less common.  Testing has not been thoroughly performed on that function, and it has been entirely removed for the v1 release.  The list of potentially workable controllers, as of 12/12/25, includes the following controllers:
  * Sony DualShock 4 (PS4) Controller
  * Sony DualSense (PS5) Controller
  * Xbox One S/X (Bluetooth) Controller
  * Switch Pro Controller
The expectation is that most people will use a phone, laptop, or similar to connect to the vehicle(s) and will use a gamepad connected to that device, which has much broader compatibility.  If demand is sufficient, we'll look at re-introducing local bluetooth controller connection and control in the future.

## Technical Information
The ESP32 controller has several main functions running on it at any given time:
* Motor control - takes gamepad or other input from a websocket and uses that to drive the motors.  Includes a safety timeout so if no control packet is received within a timeframe (about 0.2 seconds), it will cut power to the motors, ensuring the vehicle doesn't move unintentionally.
* Wifi connection - on startup, the controller will either create an AP network or connect to your home wifi network, enabling wifi control.
* LED/Function control - controls the vehicle LEDs to reflect the wifi connection status, or for other usage if the vehicle has LEDs as a function.  Also controls things like the siren, or other non-motor functions.
* Web server - hosts the various configuration pages and play page that allow a user to interact with, setup, and control the vehicle.

## Notes
Vehicle configurations are created per-vehicle.  Every vehicle will start as a default loader, with default motor configuration.  You have to go into the vehicle's configuration pages to set up that particular vehicle.  That configuration is stored in a file, so will persist between restarts.  It'll even persist if you do an OTA update of the vehicle software.  The only time you might need to reconfigure a vehicle is if you have to reflash the controller firmware, or follow directions to manually format and update the vehicle for some reason.  That shouldn't happen often.

As-is, the vehicles are individually and directly controllable by a phone or laptop.  Nothing else needed.  You'd navigate to the IP address of a specific vehicle, and control that vehicle.  This is expandable to many-vehicle setups, though you have to manually manage connecting to each vehicle.  If you have a fleet of vehicles, you may wish to look at the RokSystem project or other multiplayer-type projects, which provide a better interface for allowing control of any of the available vehicles, and more quickly switching between them.  They mostly require running a small program on a computer connected to the same network, or a raspberry pi or similar single-board computer if desired.

Opening up the vehicles to online play is possible but not expected with only the control conversion; it uses unsecured websockets, which aren't typically friendly to use externally.  The RokSystem or other projects overcome that limitation, so if you intend to use online play, I strongly suggest investigating those projects rather than opening up each individual vehicle to the internet.  Instructions for this can be found in the RokSystem project.