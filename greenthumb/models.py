from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Literal


@dataclass
class PlantSpec:
    name: str
    zone_id: str
    sensor_address: int
    moisture_target: int = 15
    watering_volume_ml: int = 100
    light_mode: Literal["off", "ambient", "cycle", "manual"] = "ambient"
    light_start_time: time = time(8, 0)
    light_stop_time: time = time(20, 0)
    position_mm: int = 0
    # Auto-managed LED segment for the global strip. This is calculated by the app,
    # not exposed to the user for manual editing.
    led_start_index: int = 0
    led_end_index: int = 0


@dataclass
class SensorSample:
    sensor_address: int
    moisture_percent: float
    temperature_c: float | None = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds"))


@dataclass
class ZoneStatus:
    zone_id: str
    moisture_percent: float
    target_moisture: float
    pump_active: bool = False
    lighting_mode: str = "ambient"
    last_watered: str | None = None
