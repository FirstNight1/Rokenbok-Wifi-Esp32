# Rokenbok-Wifi-Esp32

This project aims to replace the mainboards in Rokenbok vehicles with new microcontrollers to enable wifi connectivity for the vehicles, and control over wifi, bluetooth (limited to BLE controllers currently), and across the internet.  It also contains projects for implementing an FPV camera on each vehicle, as well as an overall system manager to orchestrate playing with and managing multiple vehicles.

## Release History:
This project has not yet been released as an official version, and is entirely a work in progress.


## Vehicle hardware conversion - Drive Base
WARNING: This conversion is not designed to be easily reversible.  You will need soldering skills, and a willingness to take your vehicle apart, including potentially damaging it irreparably.  Do not expect to be able to go back to the stock configuration/setup if something goes wrong.  Theoretically all the stock wiring is still there, and/or you could run new wire to the stock motors and vehicle keyway, and attach those back to the stock control board.

If you intend to ever reverse this modification, I would suggest taking thorough pictures of the existing wiring connections on the controller board (pictures will be included as possible from my vehicles in the Vehicle Info folder as well), and carefully de-solder the motor, LED, and key wires from the board, that way they can be re-attached.  For ease of reversal, it may be worthwhile to utilize screw terminal blocks on your breakout and control boards, which will minimize re-soldering needed of the existing small vehicle wires.


1. The Vehicle Info folder contains information and pictures of the vehicles modified so far, more pictures and information will be added as we convert more vehicles.  This information may also be useful for repairs to the vehicle.

Parts used:
2x DRV8833 breakout motor driver boards (generic)
1x SeeedStudio XIAO ESP32-S3 controller board, flashed with Micropython and then the latest RokVehicle release (Instructions included in a Readme.md in RokVehicle)
220ohm 1/4 watt resistors, if the vehicle has LEDs (optional)
1x power switch (optional)
(Wire - suggest 22 or 24ga, mounting tape or glue, solder, and other miscellanious electronics bits may be required)
(This project requires mid-level soldering skills)
2. The hardware above will enable a minimal conversion, that only alters the vehicle drive base to use the new control system.  See below sections if you want to add FPV, or eventually we will likely include instructions for power/battery modifications as well.  Currently, this setup is intended to utilize the stock alkaline batteries, and has also proven able to operate on NiMH rechargeables as well.
3. Navigate to the Vehicle Info page for the vehicle you are looking to modify.  It will contain the mechanical steps and pictures needed to disassemble the vehicle, as well as pictures of the control board.  You will need to desolder ALL wires from the existing control board, and remove that control board.
4. A wiring diagram and list is included on each vehicle information page.  You will need to follow it to determine which wires need to be connected where, and then in the root Vehicle Info folder is also a Drive Modification circuit/connection diagram to show the hookups needed.
  * In general, you will need to connect power and ground from the battery terminals to the controller board and one or two motor driver boards (most vehicles will need two motor driver boards, but may only drive 3 total motors).  I suggest routing the battery positive through a swtich first, pictures of which are on the vehicle page to install unobtrusively protruding into the battery compartment.
  * Next, you will need to make connections between the controller and the motor drivers, consisting of up to eight total control signal wires, depending on the number of motors on the given vehicle.
  * Third, you will connect the existing vehicle motor wiring to the motor drivers, consisting of two input wires per motor, and connecting any now-unconnected casing grounds to other motor casings, or the battery ground.
  * Lastly, you will connect any LEDs or accessories/non-motor functions that may be on the vehicle to remaining controller pins, as shown on the schematic.

5. After completing the hardware modifications, it is important to verify all wiring connections prior to powering on the vehicle.  Take a minute and double check your wiring against the circuit diagrams, and ensure all connections make sense (i.e. you aren't shorting the battery leads together anywhere).
6. Hopefully you flashed the software onto the controller before you put it in the vehicle, otherwise dig up a usb-c cord (right angle ones are available and can be helpful if you glued yourself into a jam) and follow those instructions in the RokVehicle project now.

7. On initial startup of a new vehicle, it will create a Wifi Access Point (AP) that looks like loader-XYZABC.  This network name is the tag for the vehicle, and consists of the vehicle type and it's unique tag.  The default vehicle type is loader, we'll update this shortly.  Connect a phone or computer to the access point.  The default password for the access point is 1234567890.  The vehicle should have an IP address of 192.168.4.1, and should assign your device an IP address of 192.168.4.2.
8. Open Chrome (or an internet browser) on the device, and navigate to http://192.168.4.1, which should load the home page for the vehicle, and show various information about the vehicle.
9. Navigate to the Admin page link in the header, which will take you to a page where you can configure the general settings for the vehicle.  Select the correct vehicle type from the list.  When you select a vehicle type from the list, it will update the tag prefix as well.  I suggest keeping the same vehicle tag, but you can also set a custom vehicle tag if desired, ensure it is unique for each vehicle.  You can also set a "friendly name" for the vehicle, useful to differentiate Power Sweeper 1 and Power Sweeper 2 if you have multiple, for example.  Click save to save your updates.  The change to the AP network name to match the new tag will NOT take effect until the vehicle is rebooted.
10. If you are going to use the AP to control the vehicle, go ahead and reboot it now by turning it off and on, or removing and replacing the batteries, and connect your device to the new AP.  If you plan to connect the vehicle to your home wifi and control it that way, then navigate to the wifi page and enter your wifi details.  By default, the vehicle will use DHCP to connect to this wifi network, though you can set a static IP on this page if needed.
  * When the vehicle boots up, it will attempt 5 times to connect to the wifi network, if configured.  If the vehicle is unable to connect to the network, it will "fall back" to AP mode, and you will see a network with the tag of the vehicle, just like in step 7.  You can use this to check and correct any errors in the wifi settings.  Or also works great if you travel with the vehicle and want to use it away from your configured network, it will quickly fall into AP mode and you can play with it that way.
NOTE: If you get stuck on a bad wifi network or set a bad static IP or similar, reboot the vehicle 3 times in rapid succession (less than 20 seconds between reboots), and it will force the vehicle into AP mode, so you can connect back and edit the wifi/IP settings.  Note that this will not clear your stored wifi network and credentials, so future reboots will still attempt to connect back to the configured network unless you make edits.
11. The vehicle should now be connected to your network, or you are using it in AP mode.  It's time to configure things for your specific vehicle hardware.  Go to the Testing page.  The browser should open a websocket to the vehicle (which emulates how a controller will control the vehicle), and then give a list of the motors present on the vehicle, and some configuration items for each: A motor port number (in case you wired your vehicle different from the schematic), a minimum power per motor (controleld on a scale from 1-65), and a reversed checkbox (used for drive or function motors if they rotate opposite the intended direction for "forward" and "reverse", for example if you forgot to reverse the wiring on one of the drive motors so it's opposite the other, or the sweeper is intaking balls on reverse rather than forward, etc.)

Go to the Play screen via the header, or the Play Now button on the home screen, and you should be able to connect a controller to your device and control the vehicle!  The Play page is explained in more detail later.




# TODO List (Project-wide)

- [ ] Remove all debug logging and print statements from all code (production cleanup)
- [ ] Refactor and clean up every class for clarity and maintainability
- [ ] Check every web page and Python file for syntax issues and errors
- [ ] Fix: Crashes in the web server cause the REPL to hang; ensure graceful error handling and recovery
- [ ] Fix: Nothing restarts gracefully after a crash; implement robust restart logic
- [ ] Fix: WiFi retry logic—if WiFi fails the first time, subsequent retries immediately fail with 'WiFi Internal Error'; ensure retries are meaningful
- [ ] Add setting a password to AP mode rather than always using 1234567890
- [ ] Add a Readme.md in RokVehicle on flashing MicroPython and this program onto the board
- [ ] Add documentation in this Readme.md on the Play page, using gamepads, assigning control methodology and buttons, using axis controllers, and connecting Bluetooth gamepads directly to the vehicle
- [ ] FPV conversion instructions and setup
- [ ] Play server instructions and setup