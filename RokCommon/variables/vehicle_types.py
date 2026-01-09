# variables/vehicle_types.py

# ---------------------------------------------------------
# Defines the various vehicle types and their motor/function configurations
# the typeFriendlyName is used for display in the admin page
# the tagName is used as a prefix when using the default vehicle Tag (does not override custom tags)
# Axis motors are motors that can be controlled variably, i.e. by an axis rather than on/off.
#   on most vehicles, these are the left and right drive motors
# Motor functions are motors that are controlled as either on or off, with no variable speed control.
#   these are typically used for functions like lifting a bed, operating a blade, etc.
# functions are additional non-motor functions that can be toggled on/off, such as lights or sirens.
# ---------------------------------------------------------

VEHICLE_TYPES = [
    {
        "typeName": "loader",
        "typeFriendlyName": "Loader",
        "tagName": "loader",
        "axis_motors": ["left", "right"],
        "motor_functions": ["bed"],
        "functions": [],
    },
    {
        "typeName": "dozer",
        "typeFriendlyName": "Dozer",
        "tagName": "dozer",
        "axis_motors": ["left", "right"],
        "motor_functions": ["blade"],
        "functions": [],
    },
    {
        "typeName": "transgripper",
        "typeFriendlyName": "Transgripper",
        "tagName": "transgripper",
        "axis_motors": ["left", "right"],
        "motor_functions": ["lift", "grab"],
        "functions": [],
    },
    {
        "typeName": "emergency_speedster",
        "typeFriendlyName": "Emergency Speedster",
        "tagName": "speedster",
        "axis_motors": ["left", "right"],
        "motor_functions": [],
        "functions": ["lights", "siren"],
    },
    {
        "typeName": "power_sweeper",
        "typeFriendlyName": "Power Sweeper",
        "tagName": "sweeper",
        "axis_motors": ["left", "right"],
        "motor_functions": ["intake", "bed"],
        "functions": [],
    },
    {
        "typeName": "skip_track",
        "typeFriendlyName": "Skip Track",
        "tagName": "skiptrack",
        "axis_motors": ["left", "right"],
        "motor_functions": ["lift"],
        "functions": [],
    },
    {
        "typeName": "elevator",
        "typeFriendlyName": "Elevator",
        "tagName": "elevator",
        "axis_motors": [],
        "motor_functions": ["updown"],
        "functions": [],
    },
    {
        "typeName": "monorail",
        "typeFriendlyName": "Monorail",
        "tagName": "monorail",
        "axis_motors": ["travel"],
        "motor_functions": ["bed"],
        "functions": [],
    },
    {
        "typeName": "tower_crane",
        "typeFriendlyName": "Tower Crane",
        "tagName": "crane",
        "axis_motors": ["rotate", "winch"],
        "motor_functions": [],
        "functions": ["trolley", "holding"],
    },
    {
        "typeName": "forklift",
        "typeFriendlyName": "Forklift",
        "tagName": "forklift",
        "axis_motors": ["left", "right"],
        "motor_functions": ["lift"],
        "functions": [],
    },
    {
        "typeName": "fire_rescue",
        "typeFriendlyName": "Fire Rescue",
        "tagName": "rescue",
        "axis_motors": ["left", "right"],
        "motor_functions": ["claw"],
        "functions": [],
    },
    {
        "typeName": "police_defender",
        "typeFriendlyName": "Police Defender",
        "tagName": "defender",
        "axis_motors": ["left", "right"],
        "motor_functions": ["raise"],
        "functions": [],
    },
    {
        "typeName": "dump_truck",
        "typeFriendlyName": "Dump Truck",
        "tagName": "dumptruck",
        "axis_motors": ["left", "right"],
        "motor_functions": ["bed"],
        "functions": [],
    },
    {
        "typeName": "x2_dual_drive",
        "typeFriendlyName": "X2 Dual Drive",
        "tagName": "x2",
        "axis_motors": ["winch", "winch2"],
        "motor_functions": [],
        "functions": [],
    },
]


def get_type(typeName):
    for t in VEHICLE_TYPES:
        if t["typeName"] == typeName:
            return t
    return VEHICLE_TYPES[0]
