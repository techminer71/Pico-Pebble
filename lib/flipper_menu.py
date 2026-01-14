# flipper_menu.py
# Basic menu system for Flipper Pico over UART

import time

class Menu:
    def __init__(self, display_callback):
        self.options = ["Payload 1", "Payload 2", "Payload 3"]
        self.index = 0
        self.display_callback = display_callback
        self.update_display()

    def update_display(self):
        # Show the menu with the current selection highlighted
        display_lines = []
        for i, option in enumerate(self.options):
            prefix = ">" if i == self.index else " "
            display_lines.append(f"{prefix} {option}")
        self.display_callback("\\n".join(display_lines))

    def move_up(self):
        if self.index > 0:
            self.index -= 1
            self.update_display()

    def move_down(self):
        if self.index < len(self.options) - 1:
            self.index += 1
            self.update_display()

    def select(self):
        selected = self.options[self.index]
        self.display_callback(f"Running {selected}")
        time.sleep(1)
        self.update_display()
