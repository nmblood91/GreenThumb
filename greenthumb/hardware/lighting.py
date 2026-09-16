from __future__ import annotations

import logging
import threading
import time
from typing import Literal

from greenthumb.hardware.led_strip import Ws2811Strip

logger = logging.getLogger(__name__)

Mode = Literal["off", "schedule", "manual", "rainbow"]
VALID_MODES = {"off", "schedule", "manual", "rainbow"}
VALID_COLOR_ORDERS = ("RGB", "RBG", "GRB", "GBR", "BRG", "BGR")

FRAME_INTERVAL = 1 / 30
IDLE_INTERVAL = 0.5


def colour_wheel(position: int) -> tuple[int, int, int]:
    position %= 256
    if position < 85:
        return (position * 3, 255 - position * 3, 0)
    if position < 170:
        position -= 85
        return (255 - position * 3, 0, position * 3)
    position -= 170
    return (0, position * 3, 255 - position * 3)


class LedController:
    """Renders lighting modes onto an addressable strip from a background thread."""

    def __init__(
        self,
        led_count: int = 20,
        strip: Ws2811Strip | None = None,
        color_order: str = "RGB",
        spi_bus: int = 0,
        spi_device: int = 0,
    ) -> None:
        self.led_count = max(int(led_count), 1)
        self.mode: Mode = "schedule"
        self.color = (0, 255, 128)
        self.brightness = 75
        self.strip = strip if strip is not None else Ws2811Strip(
            bus=spi_bus, device=spi_device, color_order=color_order
        )

        self._segments: list[tuple[int, int, bool]] = []
        self._rainbow_offset = 0
        self._last_frame: list[tuple[int, int, int]] | None = None
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread:
            return
        self._thread = threading.Thread(target=self._run, name="leds", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self.strip.close()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._render()
            except Exception:
                logger.exception("LED render failed")

            if self.mode == "rainbow":
                self._rainbow_offset = (self._rainbow_offset + 2) % 256
                time.sleep(FRAME_INTERVAL)
            else:
                # Static modes only need redrawing when something changes, so
                # wait to be woken instead of burning a core on identical frames.
                self._wake.wait(IDLE_INTERVAL)
                self._wake.clear()

    def _render(self) -> None:
        frame = self._build_frame()
        if frame == self._last_frame:
            return
        if self.strip.show(frame):
            self._last_frame = frame

    def _build_frame(self) -> list[tuple[int, int, int]]:
        if self.mode == "off":
            pixels = [(0, 0, 0)] * self.led_count
        elif self.mode == "manual":
            pixels = [self.color] * self.led_count
        elif self.mode == "rainbow":
            pixels = [
                colour_wheel(index * 256 // self.led_count + self._rainbow_offset)
                for index in range(self.led_count)
            ]
        else:
            pixels = [(0, 0, 0)] * self.led_count
            for start, end, lit in self._segments:
                if not lit:
                    continue
                for index in range(max(start, 0), min(end, self.led_count - 1) + 1):
                    pixels[index] = self.color

        scale = self.brightness / 100
        return [
            (int(red * scale), int(green * scale), int(blue * scale))
            for red, green, blue in pixels
        ]

    def set_zone_segments(self, segments: list[tuple[int, int, bool]]) -> None:
        """Which LED ranges the schedule wants lit; ignored in the other modes."""
        if segments != self._segments:
            self._segments = segments
            self._wake.set()

    def set_mode(self, mode: str) -> dict[str, str]:
        if mode not in VALID_MODES:
            raise ValueError(f"Unsupported LED mode: {mode}")
        self.mode = mode  # type: ignore[assignment]
        self._wake.set()
        return {"status": "ok", "mode": mode}

    def set_static_color(self, color: tuple[int, int, int]) -> dict[str, object]:
        self.color = color
        self.mode = "manual"
        self._wake.set()
        return {"status": "ok", "color": color, "mode": self.mode}

    def set_brightness(self, brightness: int) -> dict[str, object]:
        self.brightness = max(0, min(int(brightness), 100))
        self._wake.set()
        return {"status": "ok", "brightness": self.brightness}

    def set_color_order(self, order: str) -> dict[str, object]:
        normalised = str(order).strip().upper()
        if normalised not in VALID_COLOR_ORDERS:
            raise ValueError(f"Unsupported LED color order: {order}")
        self.strip.color_order = normalised
        # Only the wire encoding changes, not the pixel values, so the
        # unchanged-frame check would otherwise skip sending the new order.
        self._last_frame = None
        self._wake.set()
        return {"status": "ok", "color_order": normalised}

    def status(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "color": self.color,
            "brightness": self.brightness,
            "led_count": self.led_count,
            "color_order": self.strip.color_order,
            "color_order_options": list(VALID_COLOR_ORDERS),
            # Whether frames can be sent, not whether a strip is listening: the
            # data line is write-only, so an attached strip is not detectable.
            "spi_ready": self.strip.available,
            "error": self.strip.error,
        }
