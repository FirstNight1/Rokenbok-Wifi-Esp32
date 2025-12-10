import ujson as json
import os
import random
import ubinascii

CONFIG_DIR = "variables"
CONFIG_FILE = "config.json"

DEFAULT_TYPE = "vision"

def random_tag():
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.choice(chars) for _ in range(6))

def default_config():
    return {
        "deviceType": DEFAULT_TYPE,
        "deviceTag": f"{DEFAULT_TYPE}-{random_tag()}",
        "deviceName": None,
        "ssid": None,
        "wifipass": None,
        "ip_mode": "dhcp",
        "static_ip": "",
        "static_mask": "",
        "static_gw": "",
        "static_dns": "",
    }


def load_config():
    if CONFIG_DIR not in os.listdir():
        os.mkdir(CONFIG_DIR)
    files = os.listdir(CONFIG_DIR)
    full_path = f"{CONFIG_DIR}/{CONFIG_FILE}"
    if CONFIG_FILE not in files:
        cfg = default_config()
        save_config(cfg)
        return cfg
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
