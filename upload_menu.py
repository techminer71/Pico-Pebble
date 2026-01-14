import os
import yaml
import json

# Simulate the /menus/ directory
menu_dir = "./menus"
os.makedirs(menu_dir, exist_ok=True)

def convert_yaml_to_json(menu_dir):
    converted_files = []
    for fname in os.listdir(menu_dir):
        if fname.endswith(".yaml") or fname.endswith(".yml"):
            yaml_path = os.path.join(menu_dir, fname)
            json_path = os.path.join(menu_dir, fname.rsplit(".", 1)[0] + ".json")

            with open(yaml_path, "r") as yf:
                try:
                    data = yaml.safe_load(yf)
                    with open(json_path, "w") as jf:
                        json.dump(data, jf, indent=2)
                    converted_files.append(json_path)
                except yaml.YAMLError as e:
                    print(f"Error parsing {fname}: {e}")
    return converted_files

# Run the converter (simulate once for now)
converted = convert_yaml_to_json(menu_dir)
converted

