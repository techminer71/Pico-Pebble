# payloader.py (CircuitPython)
import time
import board
from spi_comm import SPIComm

PAYLOAD_DIR = "/payloads/"
spi = SPIComm(cs_pin=board.GP17, baudrate=500000)

def load_payload(name: str) -> str:
    path = PAYLOAD_DIR + name
    with open(path, "r") as f:
        data = f.read()
    # normalize newlines
    return data.replace("\r\n", "\n").replace("\r", "\n")

def sum16(b: bytes) -> int:
    return sum(b) & 0xFFFF

def send_payload(name: str, screen=None) -> bool:
    try:
        text = load_payload(name)
    except Exception as e:
        msg = f"ERR {e}"
        print(msg)
        if screen:
            screen.print_line("1: Payload error")
            screen.print_line("2: See serial")
            screen.flush()
        return False

    payload_bytes = text.encode("utf-8")
    paylen = len(payload_bytes)
    paysum = sum16(payload_bytes)

    meta = f"REM META LEN={paylen} SUM16={paysum}\n".encode("utf-8")
    full = meta + payload_bytes

    if screen:
        screen.clear()
        screen.print_line("1: Sending")
        screen.print_line(f"2: {name}")
        screen.flush()

    print(f"[PAYLOAD] {name} len={paylen} sum16={paysum}")
    print(f"[SPI] Sending {len(full)+1} bytes (META+payload+EOT)")

    spi.send_bytes(full, append_eot=True)
    time.sleep(0.05)
    return True
