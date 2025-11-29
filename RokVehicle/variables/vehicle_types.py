# variables/vehicle_types.py


VEHICLE_TYPES = [
    {
        "typeName": "loader",
        "motor_map": {
            "left":   {"motor": 1},
            "right":  {"motor": 2},
            "raise":    {"motor": 3}
        }
    },
    {
        "typeName": "transgripper",
        "motor_map": {
            "left":   {"motor": 1},
            "right":  {"motor": 2},
            "raise":    {"motor": 3},
            "grip": {"motor": 4}
        }
    },
    {
        "typeName": "sweeper",
        "motor_map": {
            "left":   {"motor": 1},
            "right":  {"motor": 2},
            "bed":    {"motor": 3},
            "intake": {"motor": 4}
        }
    }
]

def get_type(typeName):
    for t in VEHICLE_TYPES:
        if t["typeName"] == typeName:
            return t
    return VEHICLE_TYPES[0]
