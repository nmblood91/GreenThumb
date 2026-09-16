from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# WS2811 wants a 1.25us bit period where a zero holds high ~250ns and a one
# ~600ns. Clocking SPI at 3.2MHz makes each SPI bit 312ns, so four of them cover
# one data bit: 1000 is a zero (312ns high) and 1100 a one (625ns high). Four
# also divides into a byte evenly, so two data bits map onto exactly one SPI
# byte and there is no bit packing across boundaries.
SPI_HZ = 3_200_000

_BIT_PAIRS = {0b00: 0x88, 0b01: 0x8C, 0b10: 0xC8, 0b11: 0xCC}
_ENCODED_BYTES = [
    bytes(
        (
            _BIT_PAIRS[(value >> 6) & 0b11],
            _BIT_PAIRS[(value >> 4) & 0b11],
            _BIT_PAIRS[(value >> 2) & 0b11],
            _BIT_PAIRS[value & 0b11],
        )
    )
    for value in range(256)
]

# The strip latches on a long low. 42 idle bytes at 3.2MHz is ~105us, clear of
# the 50us minimum with room for clock jitter.
RESET = b"\x00" * 42


class Ws2811Strip:
    """Drives a WS2811 strip from the Pi's SPI MOSI line."""

    def __init__(self, bus: int = 0, device: int = 0, color_order: str = "RGB") -> None:
        self.color_order = color_order.upper()
        self.spi = None
        self.error: str | None = None

        try:
            import spidev

            self.spi = spidev.SpiDev()
            self.spi.open(bus, device)
            self.spi.max_speed_hz = SPI_HZ
            self.spi.mode = 0
            logger.info("LED strip ready on SPI %d.%d, order %s", bus, device, self.color_order)
        except Exception as exc:
            # Left unavailable rather than faked: the API reports the strip as
            # offline so a wiring problem is visible instead of silent.
            self.error = str(exc)
            self.spi = None
            logger.error("LED strip unavailable on SPI %d.%d: %s", bus, device, exc)

    @property
    def available(self) -> bool:
        return self.spi is not None

    def show(self, pixels: list[tuple[int, int, int]]) -> bool:
        if not self.spi:
            return False

        payload = bytearray()
        for red, green, blue in pixels:
            channels = {"R": red, "G": green, "B": blue}
            for name in self.color_order:
                payload += _ENCODED_BYTES[max(0, min(channels[name], 255))]
        payload += RESET

        try:
            self.spi.writebytes2(payload)
            return True
        except Exception as exc:
            self.error = str(exc)
            logger.error("Failed to write LED frame: %s", exc)
            return False

    def close(self) -> None:
        if self.spi:
            try:
                self.spi.close()
            except Exception:
                pass
            self.spi = None
