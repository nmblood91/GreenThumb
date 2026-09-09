from __future__ import annotations

from typing import Literal


class LedController:
    """Simple abstraction for addressable LED control. Real implementation may use rpi_ws281x or a custom protocol."""

    def __init__(self, led_count: int = 60) -> None:
        self.led_count = led_count
        self.mode: Literal["off", "ambient", "rainbow", "manual"] = "ambient"
        self.color = (0, 255, 128)

    def set_mode(self, mode: str) -> dict[str, str]:
        valid_modes = {"off", "ambient", "rainbow", "manual"}
        if mode not in valid_modes:
            raise ValueError(f"Unsupported LED mode: {mode}")
        self.mode = mode
        return {"status": "ok", "mode": mode}

    def set_static_color(self, color: tuple[int, int, int]) -> dict[str, tuple[int, int, int] | str]:
        self.color = color
        self.mode = "manual"
        return {"status": "ok", "color": color, "mode": self.mode}

    def rainbow_cycle(self) -> dict[str, str]:
        self.mode = "rainbow"
        return {"status": "ok", "mode": self.mode}
