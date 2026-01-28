import ujson as json
import os
import random

# Variables
CONFIG_DIR = "variables"
CONFIG_FILE = "config.json"
CONFIG_DEFAULTS_FILE = "config_defaults.json"
# Cache for the loaded configuration
_cached_config = None


# ---------------------------------------------------------
# Generate a random 6-character tag
# ---------------------------------------------------------
def random_tag():
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.choice(chars) for _ in range(6))


# ---------------------------------------------------------
# Validate and repair config if needed
# ---------------------------------------------------------
def validate_and_repair_config(cfg):
    """Ensure critical config fields exist, repair if missing"""
    if not isinstance(cfg, dict):
        print("ERROR: Config is not a dictionary, creating new config")
        return minimal_default_config()
    
    # Required fields that should never be missing
    required_fields = {
        "vehicleType": "RokDevice", 
        "vehicleTag": f"RokDevice-{random_tag()}",
        "vehicleName": None
    }
    
    repaired = False
    for field, default_value in required_fields.items():
        if field not in cfg:
            print(f"WARNING: Missing required field '{field}', adding default: {default_value}")
            cfg[field] = default_value
            repaired = True
    
    if repaired:
        print("Config repaired - saving updated version")
        save_config(cfg)
    
    return cfg


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
    global _cached_config

    # Check if config exists at variables/config.json
    config_dir = CONFIG_DIR
    config_file = f"{CONFIG_DIR}/{CONFIG_FILE}"
    config_defaults_file = f"{CONFIG_DIR}/{CONFIG_DEFAULTS_FILE}"

    # Ensure directory exists
    try:
        try:
            os.stat(config_dir)
        except OSError:
            os.makedirs(config_dir)
    except Exception as e:
        print(f"Config directory creation failed, fatal error: {e}")
        return None

    # Try to load existing runtime config first
    config_loaded = False
    try:
        try:
            # Check if config file exists and is readable
            os.stat(config_file)

            
            # Try to load and validate the config
            with open(config_file, "r") as f:
                content = f.read().strip()
                if not content:
                    print("WARNING: Config file is empty - preserving file and using defaults")
                    # Don't overwrite empty file, load defaults instead
                    _cached_config = None
                else:
                    try:
                        _cached_config = json.loads(content)
                        # Validate and repair config if needed
                        _cached_config = validate_and_repair_config(_cached_config)

                        config_loaded = True
                    except json.JSONDecodeError as je:
                        print(f"ERROR: Config file corrupted (JSON error): {je}")
                        print(f"Preserving original file and creating backup...")

                        _cached_config = None
                        
        except OSError:
            # Config file doesn't exist - normal first run
            print(f"Config file {config_file} not found - first run setup")
            _cached_config = None
            
    except Exception as e:
        print(f"Unexpected error reading config: {e}")
        _cached_config = None
    
    # Only load defaults if no valid config was found
    if not config_loaded:
        try:
            try:
                os.stat(config_defaults_file)
                load_config_defaults()
                if _cached_config:
                    print(f"Loaded project defaults from {config_defaults_file}")
                    # Save the defaults as runtime config
                    save_config(_cached_config)
                    config_loaded = True
            except OSError:
                # No defaults file either, use hardcoded minimal config
                print("No config files found, creating minimal default config")
                save_default_config()
                config_loaded = True
        except Exception as e:
            print(f"Config defaults loading failed: {e}")
            # Last resort - minimal config
            print("Using minimal fallback config")
            _cached_config = minimal_default_config()
            save_config(_cached_config)

    # if cached config has a default Vehicle Tag, generate a new unique one
    tag = get_config_value("vehicleTag", "")
    if tag.endswith("DEFAULT"):
        tag = tag.replace("DEFAULT", f"{random_tag()}")
        save_config_value("vehicleTag", tag)

    # One-time sync after config initialization to ensure WiFi credentials persist
    try:
        os.sync()
        print("DEBUG: Config synced to flash after initialization")
    except AttributeError:
        # os.sync() not available on all MicroPython builds
        print("DEBUG: os.sync() not available, relying on file flush")

    return _cached_config


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
            content = f.read().strip()
            if not content:
                print(f"WARNING: Config file {config_file} is empty")
                _cached_config = None
                return None
                
        _cached_config = json.loads(content)
        print(f"Config loaded successfully: {len(_cached_config)} settings")
        return _cached_config
        
    except OSError as oe:
        print(f"Config file not found: {config_file}")
        _cached_config = None
        return None
    except json.JSONDecodeError as je:
        print(f"CRITICAL: Config file JSON corrupted at line {je.lineno}, column {je.colno}: {je.msg}")
        print(f"Content preview: {content[:100]}...")
        _cached_config = None
        return None
    except Exception as e:
        print(f"Unexpected config load error: {e}")
        _cached_config = None
        return None


# ---------------------------------------------------------
# Load default configuration from project defaults file
# ---------------------------------------------------------
def load_config_defaults():
    global _cached_config
    config_defaults_file = f"{CONFIG_DIR}/{CONFIG_DEFAULTS_FILE}"

    # Try to load project defaults
    try:
        with open(config_defaults_file, "r") as f:
            _cached_config = json.load(f)
    except Exception as e:
        print(f"Config defaults load failed: {e}")
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


# ---------------------------------------------------------
# Debug function - check config file integrity  
# ---------------------------------------------------------
def check_config_integrity():
    """Debug function to check config file status"""
    config_file = f"{CONFIG_DIR}/{CONFIG_FILE}"
    
    try:
        # Check if file exists
        stat = os.stat(config_file)
        print(f"Config file exists: {config_file}")
        print(f"File size: {stat[6]} bytes")
        
        # Try to read raw content
        with open(config_file, "r") as f:
            content = f.read()
            
        print(f"Content length: {len(content)} characters")
        
        if not content.strip():
            print("ERROR: Config file is empty!")
            return False
            
        # Try to parse JSON
        try:
            cfg = json.loads(content)
            print(f"✓ Valid JSON with {len(cfg)} settings")
            
            # Check for critical fields
            critical_fields = ["vehicleType", "vehicleTag"]
            for field in critical_fields:
                if field in cfg:
                    print(f"✓ Has {field}: {cfg[field]}")
                else:
                    print(f"✗ Missing {field}")
                    
            # Check for WiFi settings
            wifi_fields = ["ssid", "wifipass", "wifiEnabled"]
            wifi_count = sum(1 for field in wifi_fields if field in cfg)
            print(f"WiFi settings: {wifi_count}/3 configured")
            
            if "ssid" in cfg:
                print(f"  SSID: {cfg['ssid']}")
            if "wifipass" in cfg:
                print(f"  Password: {'*' * len(str(cfg['wifipass']))}")
                
            return True
            
        except json.JSONDecodeError as e:
            print(f"✗ JSON Error: {e}")
            print(f"Content preview: {content[:200]}...")
            return False
            
    except OSError:
        print(f"✗ Config file not found: {config_file}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False
