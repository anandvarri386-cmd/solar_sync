import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')

DEFAULT_CONFIG = {
    "pump_name": "Smart Solar Pump AI",
    "wifi_ssid": "SolarSync_Net",
    "wifi_password": "solarpumppass",
    "voltage_calibration": 1.0,
    "current_offset": 0.0,
    "web_simulation_enabled": True
}

def load_config():
    """Loads the config file from disk. Reverts to defaults if file is missing or corrupted."""
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
            # Ensure all default keys exist
            updated = False
            for key, val in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = val
                    updated = True
            if updated:
                save_config(config)
            return config
    except Exception as e:
        print(f"Error loading config.json, restoring defaults: {e}")
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

def save_config(config):
    """Saves the config dictionary to config.json."""
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config.json: {e}")
        return False

def update_config_key(key, value):
    """Updates a single key in the config and saves it."""
    config = load_config()
    config[key] = value
    return save_config(config)
