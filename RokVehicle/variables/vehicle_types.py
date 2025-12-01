# variables/vehicle_types.py




VEHICLE_TYPES = [
    {"typeName": "loader",
     "axis_motors": ["left", "right"],
     "motor_functions": ["bed"],
     "functions": []},
    {"typeName": "dozer",
     "axis_motors": ["left", "right"],
     "motor_functions": ["lift"],
     "functions": []},
    {"typeName": "transgripper",
     "axis_motors": ["left", "right"],
     "motor_functions": ["lift", "grab"],
     "functions": []},
    {"typeName": "emergency_speedster",
     "axis_motors": ["left", "right"],
     "motor_functions": [],
     "functions": ["lights", "siren"]},
    {"typeName": "power_sweeper",
     "axis_motors": ["left", "right"],
     "motor_functions": ["intake", "bed"],
     "functions": []},
    {"typeName": "skip_track",
     "axis_motors": ["left", "right"],
     "motor_functions": ["lift"],
     "functions": []},
    {"typeName": "elevator",
     "axis_motors": [],
     "motor_functions": ["updown"],
     "functions": []},
    {"typeName": "monorail",
     "axis_motors": ["travel"],
     "motor_functions": ["bed"],
     "functions": []},
    {"typeName": "tower_crane",
     "axis_motors": ["rotate", "winch"],
     "motor_functions": [],
     "functions": ["trolley", "holding"]},
    {"typeName": "forklift",
     "axis_motors": ["left", "right"],
     "motor_functions": ["lift"],
     "functions": []},
    {"typeName": "fire_rescue",
     "axis_motors": ["left", "right"],
     "motor_functions": ["claw"],
     "functions": []},
    {"typeName": "police_defender",
     "axis_motors": ["left", "right"],
     "motor_functions": ["raise"],
     "functions": []},
    {"typeName": "dump_truck",
     "axis_motors": ["left", "right"],
     "motor_functions": ["bed"],
     "functions": []},
    {"typeName": "x2_dual_drive",
     "axis_motors": ["winch", "winch2"],
     "motor_functions": [],
     "functions": []},
]

def get_type(typeName):
    for t in VEHICLE_TYPES:
        if t["typeName"] == typeName:
            return t
    return VEHICLE_TYPES[0]
