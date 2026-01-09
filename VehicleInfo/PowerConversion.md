# Power Conversion

## Converts NiMh (rechargeable) battery to 5V for vehicle use
### Allows NiMh to replace alkalines while maintaining vehicle performance
You can still use Alkaline batteries as well with this power conversion in place, they will work like usual. Maybe better than usual.

## Prerequisites:
This modification can be performed alone, using the stock control board but allowing for alkaline-like (faster) motor speeds.  It can also be performed in conjunction with the Control and/or FPV modifications.  It is not compatible with the LiPo power conversion, which uses a slightly different power setup to enable charging.

### Hardware Needed
1x TPS61090 converter breakout (https://www.adafruit.com/product/1903 - Adafruit PowerBoost 500 Basic, $10)
Note: The PowerBoost 1000 Basic also works, and this guide's pictures are using the 1000 Basic as it was what was available at the time.

24ga wire
Optional:
1x micro slide switch (panel mount recommended, three terminals) (technically, an SPDT maintained switch) - https://a.co/d/8894whi

### Difficulty
Basic soldering equipment and skills required - soldering and unsoldering through hole wiring

## Conversion Directions
### Disassembly Required
We only need to remove the drive base and expose the battery + and - terminal wiring.
1. Remove the two screws at the rear of the vehicle, holding the grey drive base onto the vehicle body.
2. Lift the back of the gray drive base and slide the front out of it's indents, and the top of the drive base can be accessed.

### Power Conversion
All wiring is 24ga unless otherwise noted.  Connections can be made on the bare board via through-hole soldering, or by soldering on a terminal strip and soldering to that, using 0.1 pitch screw connectors, wire wrapping, etc.
1. Be gentle in handling the drive base and the top of the vehicle.  The wires are not long, and can break easily at their attachment to the circuit board.  Don't remove any glue from the circuit board.
2. Gently lift the circuit board off the drive base, exposing the gray top of the battery box.
3. Desolder (preferable) or cut the red wire coming from the battery positive terminal.
4. Solder the red wire going to the circuit board to the 5V terminal of the breakout.
5. Solder a new black wire from the negative battery terminal to the GND terminal on the breakout.
6. Solder a very short red (color optional) wire from the battery positive to the BAT terminal on the breakout.
7. Glue the breakout to the top of the battery compartment, ensuring it won't come into contact with the stock circuit board.
  - Optionally use heat shrink to encase the breakout
  - Some vehicles have standoff posts in the middle of the battery compartment which may fit a screw hole on some breakouts, and can help hold it in place
*** OPTIONAL - Adding a power switch to the vehicle ***
Note: This is the best option to turn off your vehicle and minimize power consumption in the "off" state.
  - The Control conversion and FPV conversion will eventually (they do not now) include programming to enter a low power state when idle, however that current draw will not be as low as using a power switch. However, you may decide for frequently used vehicles that you are okay with that standby power draw versus cutting the vehicle to install a switch.  Up to you.
  - TPS61090 breakouts typically have an EN pin, and an LB (low battery) pin.  The EN is a true disconnect, connecting that pin to ground will completely de-power the output and thus turn off the vehicle (0.1uA shutdown draw, lower than the stock controller sleep mode).  The LB pin is pulled high to VBat so long as the input voltage is above 3.2V, or to 0V if the battery is below 3.2V.  We'll utilize this with the power switch to have the vehicle automatically turn off when the battery is low, to protect the NiMh batteries (if you plan to use only with alkalines to get every drop out of them, a modification is noted below to disable the low-battery power off)
  - The EN terminal and LB terminal are a signal only, so can use signal-level wire, such as 30ga.  You can still use larger wire like the 24ga as well if you want.
  - WARNING: If you disable the low voltage cutoff, it is possible to over-discharge NiMh batteries, potentially permanently damaging or destroying them.
9. The best location for a power switch is on a thin and flat section of plastic.  The thinnest spot of plastic on the drive base is in the front or back, above the motors. Another option is with the slider of the switch protruding into the battery compartment. Depending on the vehicle, you may wish to put this switch elsewhere on the body of the vehicle, such as on top of the body or behind or on the side of a cab.  The vehicle specific guides may have better suggestions.  Cut out a slot with a dremel or similar tool sufficient to fit the switch you have selected.  If you want to drill a hole and put just the slide part of the switch through, 17/64" should fit.
10. Mount the switch to the vehicle with glue, screws, or press-fit.  If using glue, use sparingly as most switches are open on the sides and getting glue in there will jam the switch.
11. Solder a wire from the EN terminal to the center of the SPDT switch.
12. Solder a wire from the 'on' side of the SPDT switch, to the LB terminal.  Note: Omit this wire if you do not wish to use the auto-off on low battery functionality (Omitting this wire is NOT recommended).
13. Solder a wire from the 'off' side of the SPDT switch to the battery negative or GND terminal.
The switch should now control whether the vehicle is on or off, while obeying the low battery cutoff as well if you installed that wire in step 12.  The theory of operation is this:
Switch off -> EN terminal connected to GND/0/low, forces the board and vehicle off.
Switch on -> EN terminal connected to LB terminal.  While battery > 3.2V, LB and thus EN are high, and board and vehicle are on.  If battery < 3.2V, LB is low/0/ground, making EN low/0/ground, turns the board and vehicle off.

## Technical Information
Power calculation:
2x R260 brushed DC hobby motors for drive, 1x (or 2x) for function.
Motors are around 120mA regularly, 150mA under strain, weren't able to get past 200mA without stalling.
Stock control - <100mA
Wifi control - 100mA
FPV - 220mA

Stock/Wifi power draw (single function vehicle, ex. loader, dozer, etc.): 550mA
With FPV power draw (single function vehicle, ex. loader, dozer, etc.): 770mA
Stock/Wifi power draw (dual function vehicle, ex. street sweeper): 700mA
WIth FPV power draw (dual function vehicle): 920mA

NiMh cell minimum voltage is about 1V/cell, or 3V input.  Low battery cutoff on the PowerBoost is 3.2V, which should be sufficient to protect NiMh cells while still getting most of the charge out of them.  Need to test if voltage drop when running 4x motors and FPV and all causes this to trigger unexpectedly.

### Considered options
TPS61023 5V converter, $4. 5V regulated output from 2-5V input.  3x NiMh / 3x Alkaline will provide >1100mA output.  78-88% efficiency.  True enable/disable.  Rejected as no low battery protection.
Other options listed under Power LiPo Conversion (all can also convert but not charge from 3NiMh/Alkaline), including non-chargers
TPS63060 buck/boost converter (Adafruit VERTER), $10.  5V regulated output from 3-12V input.  500mAh out in 3-5V, 1000mAh+ out in 5-12V. True enable/disable.  No direct low battery protection, but only turns on at 3V, which is close enough.

## Notes
There are lots of power conversion options, and even ways to power this vehicle just from differing battery setups.  Options include using AA-sized lithium cells, which in series would provide 10.8V (do not do this with this board!), and then using a buck converter instead of a boost converter, or a combo converter like Adafruit's VERTER (though it's boost output is a bit low if you went back to NiMh or Alkalines).  For purposes of this guide, I suggest sticking to tried-and-true NiMh rechargeables and the recommended PowerBoost charger.