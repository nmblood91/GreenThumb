from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class KlipperClient:
    """Thin wrapper around Klipper's HTTP API for motion and status calls."""

    def __init__(self, base_url: str = "http://127.0.0.1:7125") -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=5.0)

    def status(self) -> dict[str, Any]:
        return self._request("GET", "/printer/objects/query?heater_bed&fan&toolhead&gcode_move")

    def home_axis(self, axis: str) -> dict[str, Any]:
        payload = {"script": f"G28 {axis.upper()}"}
        return self._request("POST", "/printer/gcode/script", json=payload)

    def move_relative(self, x_mm: float = 0.0, y_mm: float = 0.0, z_mm: float = 0.0) -> dict[str, Any]:
        payload = {"script": f"G91\nG1 X{x_mm} Y{y_mm} Z{z_mm} F6000\nG90"}
        return self._request("POST", "/printer/gcode/script", json=payload)

    def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self.client.request(method, f"{self.base_url}{path}", json=json)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            logger.warning("Klipper request failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def close(self) -> None:
        self.client.close()
