import time
import board
from payloader import send_payload
from ircontrol import try_handle as ir_try_handle


file1 = '/picoPebbleMenuButton.bmp'
file2 = '/picoPebbleMenuButtonSelected.bmp'
file3 = '/picoPebbleMenuButtonPressed.bmp'

class Menu:
    ###############################
    #     Initialize the menu     #
    ###############################
    def __init__(self, menus, screen):
        self.screen = screen
        self.menus = {m["title"]: m for m in menus if "title" in m}
        self.stack = []
        self.current_title = "Main Menu"
        self.index = 0
        self.debug_enabled = False
        self.render()

    ###############################
    #     Render current view     #
    ###############################

    def render(self):
        PAGE_SIZE = 4
        line_y = [0, 16, 32, 48]

        options = self.menus[self.current_title].get("options", [])
        total = len(options)
        if total == 0:
            self.screen.clear()
            self.screen.flush()
            return

        max_index = max(0, total - 1)
        self.index = min(self.index, max_index)
        start = (self.index // PAGE_SIZE) * PAGE_SIZE

        self.screen.clear()

        for row in range(PAGE_SIZE):
            global_idx = start + row
            selected = (global_idx == self.index)
            bmp = file2 if selected else file1
            y = line_y[row]

            self.screen.draw_bitmap(bmp, 0, y)
            if global_idx < total:
                name = options[global_idx]["name"]
                self.screen.draw_text(name[:19], 6, y + 7)

        self.screen.flush()

    #############################
    #     Move selection up     #
    #############################
    def move_up(self):
        if self.index > 0:
            self.index -= 1
            self.render()

    ###############################
    #     Move selection down     #
    ###############################
    def move_down(self):
        options = self.menus[self.current_title].get("options", [])
        if self.index < len(options) - 1:
            self.index += 1
            self.render()

    #####################################
    #     Select the current action     #
    #####################################
    def select(self):
        current = self.menus[self.current_title]
        option = current.get("options", [])[self.index]
        otype = option.get("type", "action")
        action = option.get("action")

        if otype == "run":
            self.screen.clear()
            self.screen.flush()
            self.screen.draw_text(f"Running {action}", 2, 30)
            self.handle_action(action)
            self.screen.flush()
            time.sleep(1)
            self.render()

        elif otype == "message":
            self.screen.clear()
            self.screen.print_line(str(action))
            self.screen.flush()
            time.sleep(1)
            self.render()

        elif otype == "menu" and action in self.menus:
            self.stack.append((self.current_title, self.index))
            self.current_title = action
            self.index = 0
            self.render()

        elif otype == "command":
            self.handle_command(action)
            self.render()

        elif otype == "action":
            self.handle_action(action)
            self.render()

    ####################################
    #     Go back to previous menu     #
    ####################################
    def back(self):
        if self.stack:
            self.current_title, self.index = self.stack.pop()
            self.render()

    ############################################
    #    Handle internal pico-only commands    #
    ############################################
    def handle_command(self, action):
        if action == "toggle_invert":
            self.screen.invert()
        elif action == "clear_screen":
            self.screen.clear()
        elif action == "toggle_debug":
            self.debug_enabled = not self.debug_enabled
            self.screen.clear()
            state = "ON" if self.debug_enabled else "OFF"
            self.screen.print_line(f"Debug: {state}")
            self.screen.flush()
            time.sleep(1)
        elif action == "reset_cursor":
            self.index = 0
            self.render()
        elif action == "invert_once":
            self.screen.invert()
            time.sleep(0.5)
            self.screen.invert()
        elif action == "reload_menu":
            self.screen.clear()
            self.screen.print_line("Reloading...")
            slef.screen.flush()
            time.sleep(0.75)

            # You would ideally re-call load_menus(screen) here
            # for now, just simulate it with:
            self.index = 0
            self.render()
        elif action == "flash_message":
            self.screen.clear()
            self.screen.print_line("1: * FLASHING *")
            self.screen.print_line("2: Message here")
            self.screen.flush()
            time.sleep(0.75)
            self.screen.clear()
            self.render()
        else:
            self.screen.clear()
            self.screen.print_line("Unknown command:")
            self.screen.print_line(str(action))
            self.screen.flush()
            time.sleep(1)

    ##############################################
    #     Placeholder for future action handler     #
    ##############################################
    def handle_action(self, action):
        self.screen.clear()

        if ir_try_handle(action, self.screen):
            return 

        if action.startswith("run:"):
            print("got to handle_action")
            payload_file = action.replace("run:", "")
            send_payload(payload_file, screen=self.screen)
        else:
            self.screen.print_line(f"Action: {action}")
        self.screen.flush()
        time.sleep(1)

