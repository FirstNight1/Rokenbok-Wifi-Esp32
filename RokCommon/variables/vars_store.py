import ujson as json
import os
import random

# Variables
CONFIG_DIR = "variables"
CONFIG_FILE = "config.json"
# Cache for the loaded configuration
_cached_config = None


# ---------------------------------------------------------
# Generate a random 6-character tag
# ---------------------------------------------------------
def random_tag():
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.choice(chars) for _ in range(6))


# ---------------------------------------------------------
# Generate minimal default configuration with only core fields
# ---------------------------------------------------------
def minimal_default_config():
    return {
        "vehicleType": "RokDevice",
        "vehicleTag": f"RokDevice-{random_tag()}",
        "vehicleName": None,
    }


# ---------------------------------------------------------
# Check config exists and is loadable, else create/load defaults
# Load config into memory cached variable to reduce filesystem operations
# Called once at startup from main.py
# ---------------------------------------------------------
def init_config():
    # Check if config exists at variables/config.json
    config_dir = CONFIG_DIR
    config_file = f"{CONFIG_DIR}/{CONFIG_FILE}"
    # Ensure directory exists
    try:
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
            save_default_config()
    except Exception as e:
        print(f"Config directory creation failed, fatal error: {e}")
        return None
    # Ensure file exists
    try:
        if not os.path.exists(config_file):
            save_default_config()
    except Exception as e:
        print(f"Config file creation failed, fatal error: {e}")
        return None

    # Load configuration
    cfg = load_config()

    # if cfg has a default Vehicle Tag, generate a new unique one
    tag = get_config_value("vehicleTag", "")
    if tag.endswith("DEFAULT"):
        tag = tag.replace("DEFAULT", f"{random_tag()}")
        save_config_value("vehicleTag", tag)
    return cfg


# ---------------------------------------------------------
# Save minimal default configuration to file
# ---------------------------------------------------------
def save_default_config():
    cfg = minimal_default_config()
    save_config(cfg)
    return cfg


# ---------------------------------------------------------
# Load configuration from root folder (loads project specific config if exists)
# ---------------------------------------------------------
def load_config():
    global _cached_config
    config_file = f"{CONFIG_DIR}/{CONFIG_FILE}"

    # Try to load existing config
    try:
        with open(config_file, "r") as f:
            _cached_config = json.load(f)
    except Exception as e:
        print(f"Config load failed: {e}")
        _cached_config = None

    return _cached_config


# ---------------------------------------------------------
# Get full configuration
# ---------------------------------------------------------
def get_config():
    global _cached_config
    return _cached_config


# ---------------------------------------------------------
# Get specific configuration value, optionally returning a default if undefined
# Assumes the caller requires (or will require) the given configuration value
# ---------------------------------------------------------
def get_config_value(key, default=None):
    global _cached_config
    if _cached_config is None:
        return default

    if key in _cached_config:
        return _cached_config[key]
    elif default is not None:
        return default
    return None


# ---------------------------------------------------------
# Save a specific configuration value
# ---------------------------------------------------------
def save_config_value(key, value):
    global _cached_config
    if _cached_config is None:
        _cached_config = minimal_default_config()

    # Modify global cache directly
    _cached_config[key] = value

    # Save to file
    config_file = f"{CONFIG_DIR}/{CONFIG_FILE}"
    try:
        with open(config_file, "w") as f:
            json.dump(_cached_config, f)
    except Exception as e:
        print(f"Config save failed: {e}")


# ---------------------------------------------------------
# Save configuration to file and update cache
# ---------------------------------------------------------
def save_config(cfg):
    global _cached_config

    # Update cache first
    _cached_config = cfg

    # Save to file
    config_file = f"{CONFIG_DIR}/{CONFIG_FILE}"

    try:
        with open(config_file, "w") as f:
            json.dump(_cached_config, f)
    except Exception as e:
        print(f"Config save failed: {e}")
