# spi_comm.py (CircuitPython)
import board
import busio
import digitalio
import time

EOT = b"\x04"

class SPIComm:
    def __init__(self, cs_pin=board.GP17, baudrate=500000, phase=0, polarity=0, cs_settle_s=0.002):
        self.cs = digitalio.DigitalInOut(cs_pin)
        self.cs.direction = digitalio.Direction.OUTPUT
        self.cs.value = True

        self.spi = busio.SPI(clock=board.GP18, MOSI=board.GP19, MISO=board.GP16)
        self.baudrate = baudrate
        self.phase = phase
        self.polarity = polarity
        self.cs_settle_s = cs_settle_s

    def send_bytes(self, payload: bytes, append_eot: bool = True) -> None:
        if append_eot and not payload.endswith(EOT):
            payload += EOT

        # Select
        self.cs.value = False
        time.sleep(self.cs_settle_s)

        while not self.spi.try_lock():
            pass
        try:
            self.spi.configure(
                baudrate=self.baudrate,
                phase=self.phase,
                polarity=self.polarity
            )
            self.spi.write(payload)
        finally:
            self.spi.unlock()
            time.sleep(self.cs_settle_s)
            self.cs.value = True

        # Small gap between transactions helps the slave
        time.sleep(0.002)

    def send(self, data, append_eot: bool = True) -> None:
        if isinstance(data, str):
            payload = data.encode("utf-8")
        elif isinstance(data, (bytes, bytearray)):
            payload = bytes(data)
        else:
            raise TypeError("SPIComm.send(): data must be str/bytes/bytearray")

        self.send_bytes(payload, append_eot=append_eot)
