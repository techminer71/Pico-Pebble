# menu_loader.py
# Dynamically builds menu structure from main_menu.json and other JSONs in the /menus/ dir

import json
import os
from flipper_menu import Menu

MENU_DIR = "/menus/"
MAIN_MENU_FILE = "main_menu.json"

##############################
#     Check if file exists     #
##############################
def file_exists(path):
    try:
        with open(path, "r"):
            return True
    except OSError:
        return False

##############################
#     Load and parse JSON file     #
##############################
def load_json_file(path):
    with open(path, "r") as f:
        return json.load(f)

##############################
#     List all non-main menu .json files     #
##############################
def get_all_menu_files():
    return [
        f for f in os.listdir(MENU_DIR)
        if f.endswith(".json") and f != MAIN_MENU_FILE
    ]

########################################
#   Extract submenu titles from main   #
########################################
def extract_defined_submenus(main_menu_data):
    titles = set()
    for menu in main_menu_data.get("menus", []):
        for option in menu.get("options", []):
            if option.get("type") == "menu":
                titles.add(option.get("action"))
    return titles

##############################################
#   Load all menus and merge into one list   #
##############################################
def load_menus(screen):
    menus = []

    # Load main_menu.json
    main_path = MENU_DIR + MAIN_MENU_FILE
    defined_titles = set()

    if file_exists(main_path):
        main_data = load_json_file(main_path)
        menus.extend(main_data.get("menus", []))
        defined_titles = extract_defined_submenus(main_data)

    # Load all other .json menus
    for fname in get_all_menu_files():
        fpath = MENU_DIR + fname
        try:
            data = load_json_file(fpath)
            for menu in data.get("menus", []):
                title = menu.get("title")
                if title and title not in defined_titles:
                    # Add shortcut to main menu
                    shortcut = {
                        "name": title,
                        "type": "menu",
                        "action": title
                    }
                    if menus:
                        menus[0].setdefault("options", []).append(shortcut)
                    else:
                        menus.append({
                            "title": "Main Menu",
                            "options": [shortcut]
                        })
                menus.append(menu)
        except Exception as e:
            if screen and screen.dt == "debug":
                screen.print_line(f"ERR: {fname}")
                screen.print_line(str(e))
                screen.flush()

    return Menu(menus=menus, screen=screen)

