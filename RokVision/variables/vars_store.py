import ujson as json
import os
import random

CONFIG_DIR = "variables"
CONFIG_FILE = "config.json"

DEFAULT_TYPE = "fpv"


def random_tag():
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.choice(chars) for _ in range(6))


def default_config():
    tag_prefix = "RokVision" if DEFAULT_TYPE == "fpv" else DEFAULT_TYPE
    return {
        "vehicleType": DEFAULT_TYPE,
        "vehicleTag": f"{tag_prefix}-{random_tag()}",
        "vehicleName": None,
        "ssid": None,
        "wifipass": None,
        "ip_mode": "dhcp",
        "static_ip": "",
        "static_mask": "",
        "static_gw": "",
        "static_dns": "",
        "motor_min": {},
        # Camera settings
        "cam_framesize": 4,  # QVGA default (320x240)
        "cam_quality": 85,
        "cam_contrast": 1,
        "cam_brightness": 0,
        "cam_saturation": 0,
        "cam_vflip": 0,
        "cam_hmirror": 0,
        "cam_rotate": 0,
        "cam_speffect": 0,  # 0 = none, 2 = grayscale, etc.
        "cam_stream_port": 8081,  # Camera stream port
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
