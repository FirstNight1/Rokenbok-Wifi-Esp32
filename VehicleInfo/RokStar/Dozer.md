# Rokenbok Dozer - RokStar Variant

## Common Issues
None

## Disassembly
### Pre-Disassembly
No specific pre-disassembly steps are required.
It is always suggested to remove the batteries from any unit being disassembled.

### Removing the Drive Base
1. Remove 2 screws securing the grey drive base at the back of the vehicle.
2. Lift the back of the gray drive base and slide the front out of it's indents, and the top of the drive base can be accessed.

## Electronics
### Motors
The Street Sweeper contains 4 motors. They are:
* 2 drive
* 1 to lift the bed, also lifts the hitch and lowers the tailgate
* 1 to drive the sweeper intake roller
Each motor is 38mm long (tail to tip of shaft), 27mm long (base to casing), and has a diameter of 23.8mm.  It has a shaft diameter of 2mm, and exposed shaft length of 7mm.  This corresponds to an R260 brushed DC motor.  They're 3V nominal motors, with a 7000RPM no load speed (+/-10%).  They accept 3-6V, with a 6V speed around 12000RPM.
Each motor utilizes 3 coupling capacitors
* 0.1uF ceramic capacitors (labeled 104)
* Casing ground to negative terminal
* negative terminal to positive terminal
* Positive terminal to casing ground
Each motor utilizes 3 wire connections
* Casing ground to battery negative
* Negative terminal to controller negative
* Postive terminal to controller positive
### Wiring
#### Bottom of Circuit Board:
1. Red - battery positive (4.5V)
2. Black - battery negative, also goes to both drive motor casings
3. Yellow/White - drive motors right and left (2x)
    - Yellow is positive
#### Top of Circuit Board:
1. Red/White - rear LEDs right and left (2x)
    - Red is positive
    - Connected at the front of the circuit board
2. Yellow/White/Gray - sweeper roller motor 
    - Yellow is positive
    - Gray is casing ground
    - Connected at the rear passenger side of the circuit board
3. Purple/Green/Gray - bed lift motor
    - Purple is positive
    - Gray is casing ground
    - Connected at the rear driver side of the circuit board
4. Brown/White/Green/Green/Yellow/Grey - RokStar receiver 
    - Brown is a shared wire with the button and IR led
    - Gray is the button output
    - Greens are the speaker
    - Yellow/White is the IR LED receiver
#### Circuit board connections
This is the wire locations if you want to reinstall the original circuit board
