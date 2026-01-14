import board
import digitalio
import busio
import time
import sys
import select
import terminalio
#time.sleep(5)
#print("booting... ")
from spi_comm import SPIComm
from payloader import load_payload
from flipper_menu import Menu
from menu_loader import load_menus
from screen import Screen
from config_loader import load_config
from sprite_api import Sprite
from ir import IRLed

#####################
#   Def Functions   #
#####################

def wrap_words(text, width):
    text = str(text).strip()
    if not text:
        return [""]

    words = text.split(" ")
    lines = []
    line = ""

    for w in words:
        #print(f"for {w} in words:")
        if w == "":
            continue

        # If the word itself is longer than width, hard-split it
        while len(w) > width:
            if line:
                lines.append(line)
                line = ""
            lines.append(w[:width])
            w = w[width:]

        # Normal word add
        if not line:
            line = w
        elif len(line) + 1 + len(w) <= width:
            line = line + " " + w
        else:
            lines.append(line)
            #print(w)
            line = w

    if line:
        lines.append(line)

    return lines


###########################
#     Initialize Pins     #
###########################

PINUP = digitalio.DigitalInOut(board.GP2)
PINDOWN = digitalio.DigitalInOut(board.GP3)
PINRIGHT = digitalio.DigitalInOut(board.GP4)
PINLEFT = digitalio.DigitalInOut(board.GP5)
PINSELECT = digitalio.DigitalInOut(board.GP8)
PINBACK = digitalio.DigitalInOut(board.GP9)

####################################
#     Set Pins to default high     #
####################################

PINUP.direction = digitalio.Direction.INPUT
PINDOWN.direction = digitalio.Direction.INPUT
PINRIGHT.direction = digitalio.Direction.INPUT
PINLEFT.direction = digitalio.Direction.INPUT
PINSELECT.direction = digitalio.Direction.INPUT
PINBACK.direction = digitalio.Direction.INPUT

###############################
#     Set pins to pull up     #
###############################

PINUP.pull = digitalio.Pull.UP
PINDOWN.pull = digitalio.Pull.UP
PINRIGHT.pull = digitalio.Pull.UP
PINLEFT.pull = digitalio.Pull.UP
PINSELECT.pull = digitalio.Pull.UP
PINBACK.pull = digitalio.Pull.UP

config = load_config()

if config["debug_mode"]:
    debugmsg = True
    print("Debug mode is ON")

###################################
#     Initialize UART Display     #
###################################
TX = board.GP0
RX = board.GP1
uart = busio.UART(tx=TX, rx=RX, baudrate=9600, timeout=0.1)

##################################
#     Initialize I2C Display     #
##################################
# i2c = busio.I2C(board.GP7, board.GP6)
# while not i2c.try_lock():
#     pass
# if config["debug_mode"]:
#     print("Scanning I2C bus...")
# devices = i2c.scan()
# if config["debug_mode"]:
#     print("Found I2C devices:", [hex(d) for d in devices])
# i2c.unlock()

################################################
#     Initialize Screen with config values     #
################################################
screen = Screen(
    uart,
    display_type = config["display_type"],
    i2c = None,
    address=int(config["i2c_address"], 16)
)
screen.clear()

#spi = SPIComm(board.GP17)

if config["invert_on_start"]:
    screen.invert()


####################################################
#                New Draw Functions                #
####################################################
#screen.draw(15)                                   #
#  Draw Circle      R    x      y    filled        #
# screen.draw_elipse(45, 128/2, 64/2, True)        #
# screen.draw_elipse(10)                           #
# screen.draw_elipse(10, 92, 64/2)                 #
#screen.draw_rect(20, 20, 64-10, 32-10, True)      #
#screen.draw_rect(20, 10, 32, 16, False)           #
#screen.draw_text("Hello World!", 5, 10)           #
# screen.draw_bitmap(file1, 0, line1)              #
# screen.draw_text("Hello World!", 6, line1 + 7)   #
####################################################





################################
#     Send Welcome Message     #
################################


################################
#     Intro (instead of text)  #
################################
# sprite1 = Sprite.from_config(screen, "sprites/pebble.json", x=130, y=44)

# sprite1.tgmove("walk", dx=-120, dy=0, speed=70)
# sprite1.tgwait("idle", 2.0)
# sprite1.tgwait("sit", 2.0)

sprite2 = Sprite.from_config(screen, "sprites/otter.json", x=130, y=-30)

sprite2.tgmove("run", dx=-275, dy=0, speed=150)
sprite2.tgwait("sleep", 0.5)
sprite2.tgmove("run", dx=275, dy=0, speed=150)
sprite2.tgwait("sleep", 0.5)
sprite2.tgmove("run", dx=-100, dy=0, speed=150)
sprite2.tgmove("jump", dx=-10, dy=-15, speed=50)
sprite2.tgmove("jump", dx=-5, dy=0, speed=50)
sprite2.tgmove("jump", dx=-10, dy=15, speed=50)
sprite2.tgwait("land", 0.5)
sprite2.tgwait("idle-alt", 2.0)
sprite2.tgwait("sleep", 2.0)
sprite2.set_pos(140, 0)

ir = IRLed(board.GP22)
ir.blink(times=5, on_time=0.2, off_time=0.2)
ir.deinit()


################################
#   Fallback Welcome message   #
################################
if config.get("boot_message"):
    msg = str(config["boot_message"])

    # Calculate max characters per line based on font + display width
    fw, _ = terminalio.FONT.get_bounding_box()
    max_chars = max(1, screen.display.width // fw)

    lines = wrap_words(msg, max_chars)

    screen.print_line("1:" + (lines[0] if len(lines) > 0 else ""))
    screen.print_line("2:" + (lines[1] if len(lines) > 1 else ""))
    screen.flush()
    time.sleep(3)

def display(msg):
    screen.print_line(msg)
    screen.flush()

# def run_payload(name):
#    data = load_payload(name)
#    if data.startswith("ERROR:"):
#        display("1: Failed payload")
#        display(f"2: {name}")
#        return
#    display(f"1: Running")
#    display(f"2: {name}")
#    spi.send(data)
    
################################################
#     Returns a Menu instance ready to use     #
################################################
try:
    menu = load_menus(screen)
    # screen.print_line("1: Menu Loaded!")
    # screen.flush()
except Exception as e:
    screen.print_line("1: Failed to load menu!")
    screen.print_line(f"2: {str(e)}")
    screen.flush()
    raise

#####################
#     Main loop     #
#####################
while True:
    data = uart.read(1)  # Read one byte

    if not data:
        try:
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                char = sys.stdin.read()
                data = char.encode('utf-8')
        except Exception:
            pass
    # Serial input handling
    if data:
        char = data.decode('utf-8').strip().lower()
        if config["debug_mode"]:
            print(f"Char: {char}")
        if char == 'u':
            menu.move_up()
        if char == 'd':
            menu.move_down()
        if char == 's':
            menu.select()
        if char == 'b':
            menu.back()
        #if char not in ('', '\n', '\r', 'u', 'd', 's', 'b'):
        #    screen.print_line(f"1: Unknown input:")
        #    screen.print_line(f"2: {char}")
        #    screen.flush()

    # Physical button checks (run every cycle)
    if not PINUP.value:
        print("UP button pressed")
        menu.move_up()
        time.sleep(0.2)
    if not PINDOWN.value:
        print("Down button pressed")
        menu.move_down()
        time.sleep(0.2)
    if not PINSELECT.value:
        print("Select button pressed")
        menu.select()
        time.sleep(0.2)
    if not PINBACK.value:
        print("Back button pressed")
        menu.back()
        time.sleep(0.2)

    time.sleep(0.05)


