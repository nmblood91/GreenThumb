from __future__ import annotations

import time


class PumpController:
    """Simplified pump driver. Real deployment should use GPIO pins or a relay driver with a safety interlock."""

    def __init__(self, pin: int = 17) -> None:
        self.pin = pin
        self.is_running = False

    def start(self) -> dict[str, bool | int]:
        self.is_running = True
        return {"status": "ok", "pin": self.pin, "active": self.is_running}

    def stop(self) -> dict[str, bool | int]:
        self.is_running = False
        return {"status": "ok", "pin": self.pin, "active": self.is_running}

    def deliver_ml(self, volume_ml: int = 180, flow_ml_per_second: float = 2.5) -> dict[str, float | int | str]:
        duration_seconds = max(volume_ml / flow_ml_per_second, 0.1)
        self.start()
        time.sleep(duration_seconds)
        self.stop()
        return {
            "status": "ok",
            "volume_ml": volume_ml,
            "duration_seconds": round(duration_seconds, 2),
        }
