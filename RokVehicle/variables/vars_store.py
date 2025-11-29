import ujson as json
import os
import random

CONFIG_DIR = "variables"
CONFIG_FILE = "config.json"

DEFAULT_TYPE = "loader"

def random_tag():
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.choice(chars) for _ in range(6))

def default_config():
    return {
        "vehicleType": DEFAULT_TYPE,
        "vehicleTag": f"{DEFAULT_TYPE}-{random_tag()}",
        "vehicleName": None,
        "ssid": None,
        "wifipass": None,
        # per-motor minimum duty (u16) mapping by motor name. Values are
        # duty_u16 (0..65535). If a motor name is missing here, the
        # MotorController will assume a safe default (40000).
        "motor_min": {},
    }

def load_config():
    # Ensure directory exists
    if CONFIG_DIR not in os.listdir():
        os.mkdir(CONFIG_DIR)

    # Check for the config file inside the directory
    files = os.listdir(CONFIG_DIR)
    full_path = f"{CONFIG_DIR}/{CONFIG_FILE}"

    # If file missing, create default and save it
    if CONFIG_FILE not in files:
        cfg = default_config()
        save_config(cfg)
        return cfg

    # Try to load config
    try:
        with open(full_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print("Config load failed, regenerating defaults:", e)
        cfg = default_config()
        save_config(cfg)
        return cfg


def save_config(cfg):
    full_path = f"{CONFIG_DIR}/{CONFIG_FILE}"

    with open(full_path, "w") as f:
        json.dump(cfg, f)