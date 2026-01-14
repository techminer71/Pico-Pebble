import time
import board
import busio
import displayio
import terminalio
import math
from adafruit_display_text import label
from fourwire import FourWire
from adafruit_displayio_sh1106 import SH1106

WIDTH = 128
HEIGHT = 64
BORDER = 5

class Screen:
    def __init__(self, uart, display_type, i2c=None, address=0x27):
        print(f"[DEBUG] screen initialized")
        self.uart = uart
        self.dt = display_type
        self.buffer = ["", ""]

        if self.dt == "oled":
            displayio.release_displays()
            spi = busio.SPI(clock=board.GP10, MOSI=board.GP11)
            dc = board.GP13
            cs = board.GP14
            reset = board.GP12
            display_bus = FourWire(spi, command=dc, chip_select=cs, reset=reset)
            self.display = SH1106(display_bus, width=WIDTH, height=HEIGHT, col_offset=2)
            self.splash = displayio.Group()
            self.display.root_group = self.splash

            self.line_labels = [
                label.Label(terminalio.FONT, text="", x=0, y=10),
                label.Label(terminalio.FONT, text="", x=0, y=25)
            ]
            for lbl in self.line_labels:
                self.splash.append(lbl)

    def print_line(self, msg):
        if msg.startswith("1:"):
            self.buffer[0] = msg[2:].strip()
        elif msg.startswith("2:"):
            self.buffer[1] = msg[2:].strip()
        else:
            self.buffer[0] = msg.strip()
        self.update_display()

    def flush(self):
        self.update_display()

    def update_display(self):
        if self.dt == "oled":
            self.line_labels[0].text = self.buffer[0]
            self.line_labels[1].text = self.buffer[1]

    def clear(self):
        self.buffer = ["", ""]
        self.update_display()

    def invert(self):
        if self.dt == "oled":
            self.display.invert = not self.display.invert
    
    def draw(self, xpos, ypos):

        pixel_bitmap = displayio.Bitmap(1, 1, 2) #width and height here are the true size of the object
        pixel_palette = displayio.Palette(1)
        pixel_palette[0] = 0xFFFFFF # White
        pixel_bitmap[0, 0] = 1
        pixel_sprite = displayio.TileGrid(
            pixel_bitmap, pixel_shader=pixel_palette, x=xpos, y=ypos # x and y here are the origin starting from the top left
        )
        self.splash.append(pixel_sprite)

        # text = "Hello World!"
        # text_area = label.Label(
        #     terminalio.FONT, text=text, color=0xFFFFFF, x=28, y=HEIGHT // 2 - 1
        # )
        # self.splash.append(text_area)

    def draw_elipse(self, d, xpos=0, ypos=0, filled=False):
        cir_bitmap = displayio.Bitmap(d+1, d+1, 2)
        cir_palette = displayio.Palette(2)
        cir_palette[1] = 0xFFFFFF
        cir_palette[0] = 0x000000
        x = 0
        y = 0
        r = d//2
        eps = d / 2
        center = [d // 2, d // 2]
        for x in range(d+1):
            for y in range(d+1):
                sqDist = (r - r)**2 + (0 - r)**2

                if filled == False:
                    if (math.fabs((r - y)**2 + (r - x)**2 - sqDist) < eps):
                        #print("on, x, y", x, y)
                        cir_bitmap[x, y] = 1
                    else:
                        #
                        # print("off")
                        cir_bitmap[x, y] = 0
                else:
                    if ((r - y)**2 + (r - x)**2 < sqDist):
                        #print("on, x, y", x, y)
                        cir_bitmap[x, y] = 1
                    else:
                        #
                        # print("off")
                        cir_bitmap[x, y] = 0
            # y = center[1] + math.sqrt((width // 2)**2 - (x - center[0])**2)
            # print(int(y))
            # cir_bitmap[x, int(y)] = 1
            # #y = center[1] - math.sqrt((width // 2)**2 - (x - center[0])**2)
            # #print(int(y))
            # #cir_bitmap[x, int(y)] = 1
        cir_sprite = displayio.TileGrid(
            cir_bitmap, pixel_shader=cir_palette, x=(int(xpos)-r), y=int((ypos)-r)
        )
        self.splash.append(cir_sprite)

    def draw_rect(self, width, height, xpos=0, ypos=0, filled=False):
        rect_bitmap = displayio.Bitmap(width, height, 2)
        rect_palette = displayio.Palette(2)
        rect_palette[0] = 0x000000
        rect_palette[1] = 0xFFFFFF
        for x in range(width):
            for y in range(height):
                if filled == False:
                    #print("true: ")
                    if x == 0 or x == width - 1 or y == 0 or y == height - 1:
                        print("y = ", y)
                        rect_bitmap[x, y] = 1
                    else:
                        #print("x and y = ", x, y)
                        rect_bitmap[x, y] = 0
                else:
                    rect_bitmap[x, y] = 1
        rect_sprite = displayio.TileGrid(
            rect_bitmap, pixel_shader=rect_palette, x=int(xpos), y=int(ypos)
        )
        self.splash.append(rect_sprite)

    def draw_text(self, text, xpos=0, ypos=0):
        text_area = label.Label(
            terminalio.FONT, text=text, color=0xFFFFFF, x=xpos, y=ypos
        )
        self.splash.append(text_area)
    
    def draw_bitmap(self, bmpfile, xpos=0, ypos=0):
        self.display.brightness=0
        #splash = displayio.Group()
        #self.display.root_group = splash

        odb = displayio.OnDiskBitmap(bmpfile)
        face = displayio.TileGrid(odb, pixel_shader=odb.pixel_shader, x=xpos, y=ypos)
        self.splash.append(face)

        self.display.refresh(target_frames_per_second=60)

        for i in range(100):
            self.display.brightness = 0.01 * i
            #time.sleep(0.05)