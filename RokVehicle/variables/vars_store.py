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
        "ip_mode": "dhcp",
        "static_ip": "",
        "static_mask": "",
        "static_gw": "",
        "static_dns": "",
        "motor_min": {},
        "ota_github_url": "https://github.com/FirstNight1/Rokenbok-Wifi-Esp32/tree/main/RokVehicle",
        "ota_auto_backup": True,
        "ota_last_update": None,
    }


# --- Password encryption helpers ---
import ubinascii


def encrypt_password(pw):
    key = b"rokadminpw"
    data = pw.encode()
    key = (key * ((len(data) // len(key)) + 1))[: len(data)]
    enc = bytes([a ^ b for a, b in zip(data, key)])
    return ubinascii.b2a_base64(enc).decode().strip()


def check_password(pw, enc):
    key = b"rokadminpw"
    try:
        enc_bytes = ubinascii.a2b_base64(enc)
        key = (key * ((len(enc_bytes) // len(key)) + 1))[: len(enc_bytes)]
        dec = bytes([a ^ b for a, b in zip(enc_bytes, key)]).decode()
        return pw == dec
    except Exception:
        return False


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
