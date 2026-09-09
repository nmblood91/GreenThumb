from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class PlantSpec:
    name: str
    zone_id: str
    sensor_address: int
    moisture_target: float = 45.0
    watering_volume_ml: int = 180
    light_mode: Literal["off", "ambient", "cycle", "manual"] = "ambient"
    light_hours: tuple[int, int] = (8, 20)


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
