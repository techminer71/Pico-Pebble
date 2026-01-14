# config_loader.py
# Loads /config.json and provides configuration dictionary

import json

#################################
#     Default Configuration     #
#################################
DEFAULT_CONFIG = {
    "display_type": "lcd",
    "i2c_address": "0x27",
    "invert_on_start": False,
    "boot_message": "Welcome to Pico Pebble",
    "debug_mode": False
}

###############################
#     Path to config file     #
###############################
CONFIG_PATH = "/config.json"

########################################
#     Load and merge configuration     #
########################################
def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
            # Merge defaults with overrides
            config = DEFAULT_CONFIG.copy()
            config.update(data)
            return config
    except Exception as e:
        print("Failed to load config.json:", e)
        return DEFAULT_CONFIG

