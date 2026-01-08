# Rokenbok Vehicle General Information

## Motors
Most vehicles use R260 brushed motors.
38mm long (tail to tip of shaft)
27mm long (base to casing)
23.8mm diameter
2mm shaft diameter
7mm exposed shaft length
3-6V
3V: 7000 RPM no load speed (+/-10%)
6V: 12000 RPM no load speed (+/10%)

Each motor utilizes 3 coupling capacitors
* 0.1uF ceramic capacitors (labeled 104)
* Casing ground to negative terminal
* negative terminal to positive terminal
* Positive terminal to casing ground
Each motor utilizes 3 wire connections
* Casing ground to battery negative
* Negative terminal to controller negative
* Positive terminal to controller positive

## Gearing
TBD

## Lubrication
Gears come with oil/grease from the factory, but generally are worth re-greasing if you are taking the vehicle apart, at least the easily exposed gearing.
Oil: Super Lube 51004 (51010, 51030 are other sizes) Multi-Purpose Synthetic Oil with PTFE
Grease: Super Lube 21030 Multi-Purpose Synthetic Grease with PTFE
I prefer the oil to the grease, but for low-engagement gearing

## Wiring
Power and motor wires are 0.5mm diameter stranded copper, or about 24AWG.  24ga wire can be found in a variety of colors from many suppliers.  Options for repairing wire include:
1. Best - Replace the entire run.  Solder new wire onto the two endpoints - motor terminal, circuit board, etc.
2. Use a 26-24ga solder seal connector (https://a.co/d/f80x6Jz for example).  Requires a heat gun.
3. Use a 26-24ga heat shrink butt splice (https://a.co/d/dQL0er9 for example).  Requires a crimper, heat shrink can be shrunk with a lighter applied carefully.
4. Solder the wires together and cover with heat shrink, or in a pinch, electrical tape
5. Please don't just twist and tape the wires, that connection won't stand up to the vibration of the vehicle.
Signal wires (example from RokStar Receiver) are smaller, likely 28ga.

### Stock Circuit board:
#### Bottom of the circuit board
1. Red - battery positive - labelled +6V
2. Black - battery negative, also goes to both drive motor casings - labelled VSS
3. Yellow/White - drive motors right and left (2x) - labelled JP3 for right and JP4 for left
    - Yellow is positive
#### Top of the circuit board
1. Color/White - rear LEDs right and left (2x)
    - Red/Yellow/Color is positive
    - Connected at the front of the circuit board, labelled LED1 and LED2
2. Yellow/White/Gray - Third function
    - Yellow is positive
    - Gray is casing ground - connected to GND1
    - Yellow/White - connected at the rear driver side of the circuit board, labelled JP5 (printing on top side of board)
3. Purple/Green/Gray - Fourth function (some vehicles only)
    - Purple is positive
    - Gray is casing ground
    - Connected at the rear passenger side of the circuit board, labelled JP6 (printing on top side of board, likely under square yellow component F1)
    - NOTE: Motor driver IC seems to not be populated on boards without a 4th function
4. Brown/White/Green/Green/Yellow/Grey - RokStar receiver (smaller gauge wire)
    - Brown is ground, shared with the button and IR led - connected to GND at bottom of board
    - Gray is the button output - connected next to R7 
    - Greens are the speaker - labelled SPK+ and - (printing on top side of board)
    - Yellow is the IR LED receiver - connected next to R12
    - White is the IR LED receiver - connected next to GND1
