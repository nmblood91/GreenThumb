from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time


@dataclass
class ZoneSpec:
    name: str
    zone_id: str
    sensor_address: int
    # Required rather than defaulted: every zone sets these, and a default that
    # no caller uses is a value nobody notices is wrong.
    moisture_target: int
    watering_volume_ml: int
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
    moisture_raw: float = -1.0
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
