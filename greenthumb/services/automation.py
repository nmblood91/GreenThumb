from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, time, timedelta

from greenthumb.config import settings
from greenthumb.hardware.klipper_client import KlipperClient
from greenthumb.hardware.lighting import LedController
from greenthumb.hardware.pump import PumpController
from greenthumb.hardware.soil_sensors import SoilSensorHub, unavailable_sample
from greenthumb.models import SensorSample, ZoneSpec, ZoneStatus

logger = logging.getLogger(__name__)


class HardwareBusyError(RuntimeError):
    """Raised when the gantry, pump, or I2C bus is already in use."""


class GreenThumbAutomation:
    """Application service that coordinates sensors, watering, lighting, and movement."""

    def __init__(
        self,
        sensor_hub: SoilSensorHub | None = None,
        klipper_client: KlipperClient | None = None,
        pump: PumpController | None = None,
        leds: LedController | None = None,
    ) -> None:
        self.sensor_hub = sensor_hub or SoilSensorHub(
            addresses=settings.moisture_sensor_addresses_list,
            raw_dry=settings.moisture_raw_dry,
            raw_wet=settings.moisture_raw_wet,
        )
        self.klipper = klipper_client or KlipperClient(socket_path=settings.klipper_host)
        self.pump = pump or PumpController(
            self.klipper,
            pin_name=settings.pump_pin_name,
            flow_ml_per_second=settings.pump_flow_ml_per_second,
        )
        self.leds = leds or LedController(led_count=settings.led_count)

        # The gantry, the pump, and the I2C bus all tolerate exactly one user at
        # a time, and a watering cycle holds them for minutes. A single lock for
        # all three is what keeps the control loop and manual commands apart.
        self._hardware_lock = threading.Lock()
        self._history: dict[int, deque[float]] = {
            address: deque(maxlen=settings.moisture_window_size)
            for address in self.sensor_hub.addresses
        }
        self._latest: dict[int, SensorSample] = {
            address: unavailable_sample(address) for address in self.sensor_hub.addresses
        }
        self._last_watered: dict[str, datetime] = {}

        self.zones = [
            ZoneSpec(name="Zone 1", zone_id="zone_1", sensor_address=0x36, moisture_target=45, watering_volume_ml=180, light_start_time=time(8, 0), light_stop_time=time(20, 0), position_mm=150),
            ZoneSpec(name="Zone 2", zone_id="zone_2", sensor_address=0x37, moisture_target=42, watering_volume_ml=170, light_start_time=time(8, 0), light_stop_time=time(20, 0), position_mm=400),
            ZoneSpec(name="Zone 3", zone_id="zone_3", sensor_address=0x38, moisture_target=48, watering_volume_ml=190, light_start_time=time(8, 0), light_stop_time=time(20, 0), position_mm=650),
            ZoneSpec(name="Zone 4", zone_id="zone_4", sensor_address=0x39, moisture_target=44, watering_volume_ml=175, light_start_time=time(8, 0), light_stop_time=time(20, 0), position_mm=900),
        ]
        self.apply_default_led_ranges()

    def apply_default_led_ranges(self) -> None:
        zone_count = len(self.zones)
        if zone_count == 0:
            return

        total_leds = max(settings.led_count, 1)
        segment_length = total_leds // zone_count
        remainder = total_leds % zone_count

        start_index = 0
        for index, zone in enumerate(self.zones):
            segment_size = segment_length + (1 if index < remainder else 0)
            zone.led_start_index = start_index
            zone.led_end_index = start_index + segment_size - 1
            start_index += segment_size

        if self.zones:
            self.zones[-1].led_end_index = total_leds - 1

    def usable_travel_mm(self) -> float:
        """Reachable X range, where 0 is the first position the carriage can occupy."""
        rail_length = max(float(settings.gantry_rail_length_mm), 1.0)
        margin = max(float(settings.gantry_position_margin_mm), 0.0)
        return max(rail_length - (margin * 2), 1.0)

    def apply_default_zone_positions(self) -> None:
        if not self.zones:
            return

        usable_length = self.usable_travel_mm()
        zone_count = len(self.zones)

        for index, zone in enumerate(self.zones):
            ratio = (index + 1) / (zone_count + 1)
            zone.position_mm = round(usable_length * ratio, 1)

    def get_zone_positions(self) -> list[dict[str, object]]:
        return [{
            "zone_id": zone.zone_id,
            "name": zone.name,
            "position_mm": zone.position_mm,
        } for zone in self.zones]

    def set_zone_position(self, zone_id: str, position_mm: float) -> dict[str, object]:
        zone = next((item for item in self.zones if item.zone_id == zone_id), None)
        if zone is None:
            raise ValueError(f"Unknown zone_id: {zone_id}")

        bounded_position = max(0.0, min(float(position_mm), self.usable_travel_mm()))
        zone.position_mm = round(bounded_position, 1)

        return {
            "status": "ok",
            "zone_id": zone_id,
            "position_mm": zone.position_mm,
        }

    @contextmanager
    def _exclusive(self, what: str) -> Iterator[None]:
        # Fail fast rather than queue: a manual command that waited its turn
        # behind a watering cycle would run minutes after the button was pressed,
        # and a backed-up control loop would water the same zone repeatedly.
        if not self._hardware_lock.acquire(blocking=False):
            raise HardwareBusyError(f"{what} rejected: hardware is busy")
        try:
            yield
        finally:
            self._hardware_lock.release()

    def tick(self) -> None:
        """One pass of the control loop: read every sensor, then water what needs it."""
        try:
            with self._exclusive("Control loop tick"):
                self._poll_sensors()
                if settings.auto_watering_enabled:
                    self._run_watering_cycle()
        except HardwareBusyError:
            logger.info("Skipping control loop tick, hardware is busy")
        except Exception:
            # A scheduler job that raises stops being rescheduled, which would
            # silently end all polling.
            logger.exception("Control loop tick failed")

    def _poll_sensors(self) -> None:
        for address in self.sensor_hub.addresses:
            sample = self.sensor_hub.read_one(address)
            self._latest[address] = sample
            if sample.moisture_raw >= 0:
                self._history[address].append(sample.moisture_raw)

    def smoothed_percent(self, address: int) -> float:
        """Mean moisture over the window; this, not a single read, drives watering."""
        window = self._history.get(address)
        if not window:
            return -1.0
        return self.sensor_hub.raw_to_percent(sum(window) / len(window))

    def _run_watering_cycle(self) -> None:
        for zone in self.zones:
            window = self._history.get(zone.sensor_address)
            # Only act on a full window, so neither a single bad reading nor the
            # first minutes after a restart can start the pump.
            if not window or len(window) < window.maxlen:
                continue

            moisture = self.smoothed_percent(zone.sensor_address)
            if moisture >= zone.moisture_target:
                continue
            if not self._cooldown_elapsed(zone.zone_id):
                continue

            logger.info(
                "Zone %s at %.1f%% is below target %.1f%%, watering",
                zone.zone_id,
                moisture,
                zone.moisture_target,
            )
            self._move_and_water(zone)

    def _cooldown_elapsed(self, zone_id: str) -> bool:
        # Soil needs time to wick, and the window needs a full cycle to reflect
        # the change. Without this the loop would water every tick until the
        # average caught up, which is how a plant drowns.
        last = self._last_watered.get(zone_id)
        if last is None:
            return True
        return datetime.now() - last >= timedelta(minutes=settings.watering_cooldown_minutes)

    def _move_and_water(self, zone: ZoneSpec) -> dict[str, object]:
        move = self.klipper.move_gantry_absolute(zone.position_mm)
        if not move.get("ok"):
            logger.warning(
                "Not watering %s: gantry move failed (%s)", zone.zone_id, move.get("error")
            )
            return {"status": "error", "zone_id": zone.zone_id, "error": move.get("error")}

        self.pump.deliver_ml(zone.watering_volume_ml)
        self._last_watered[zone.zone_id] = datetime.now()
        return {"status": "ok", "zone_id": zone.zone_id, "volume_ml": zone.watering_volume_ml}

    def _last_watered_iso(self, zone_id: str) -> str | None:
        last = self._last_watered.get(zone_id)
        return last.isoformat(timespec="seconds") if last else None

    def get_overview(self) -> dict[str, object]:
        zone_status = [
            ZoneStatus(
                zone_id=spec.zone_id,
                moisture_percent=self.smoothed_percent(spec.sensor_address),
                target_moisture=spec.moisture_target,
                pump_active=self.pump.is_running,
                lighting_mode=self.leds.mode,
                last_watered=self._last_watered_iso(spec.zone_id),
            )
            for spec in self.zones
        ]

        return {
            "app": settings.app_name,
            "movement": self.klipper.status(),
            "zones": [status.__dict__ for status in zone_status],
        }

    def read_sensors(self) -> list[dict[str, object]]:
        """Last polled reading per sensor; the control loop owns the I2C bus."""
        return [
            {
                **self._latest[address].__dict__,
                "moisture_percent_avg": self.smoothed_percent(address),
                "sample_count": len(self._history[address]),
            }
            for address in self.sensor_hub.addresses
        ]

    def water_zone(self, zone_id: str, volume_ml: int = 180) -> dict[str, object]:
        with self._exclusive(f"Watering {zone_id}"):
            self.pump.deliver_ml(volume_ml)
            self._last_watered[zone_id] = datetime.now()
        return {"status": "ok", "zone_id": zone_id, "volume_ml": volume_ml}

    def set_light_mode(self, mode: str) -> dict[str, object]:
        result = self.leds.set_mode(mode)
        return {"status": "ok", "mode": result["mode"]}

    def set_light_color(self, color: tuple[int, int, int]) -> dict[str, object]:
        result = self.leds.set_static_color(color)
        return {
            "status": "ok",
            "mode": result["mode"],
            "color": result["color"],
        }

    def set_light_brightness(self, brightness: int) -> dict[str, object]:
        result = self.leds.set_brightness(brightness)
        return {
            "status": "ok",
            "brightness": result["brightness"],
        }

    def home_motion_axis(self, axis: str) -> dict[str, object]:
        with self._exclusive(f"Homing {axis}"):
            return self.klipper.home_axis(axis)

    def home_gantry(self) -> dict[str, object]:
        with self._exclusive("Homing gantry"):
            return self.klipper.home_gantry()

    def move_axis_relative(self, x_mm: float = 0.0, y_mm: float = 0.0, z_mm: float = 0.0) -> dict[str, object]:
        with self._exclusive("Axis move"):
            return self.klipper.move_relative(x_mm=x_mm, y_mm=y_mm, z_mm=z_mm)

    def move_gantry_relative(self, distance_mm: float) -> dict[str, object]:
        with self._exclusive("Gantry move"):
            return self.klipper.move_gantry_relative(distance_mm)

    def move_to_zone(self, zone_id: str) -> dict[str, object]:
        zone = next((item for item in self.zones if item.zone_id == zone_id), None)
        if zone is None:
            raise ValueError(f"Unknown zone_id: {zone_id}")

        with self._exclusive(f"Move to {zone_id}"):
            return self.klipper.move_gantry_absolute(zone.position_mm)

    def get_zone(self, zone_id: str) -> ZoneSpec | None:
        return next((zone for zone in self.zones if zone.zone_id == zone_id), None)

    def update_zone_plant(self, zone_id: str, name: str) -> dict[str, object]:
        zone = self.get_zone(zone_id)
        if zone is None:
            raise ValueError(f"Unknown zone_id: {zone_id}")
        zone.name = name.strip() or zone.name
        return {"status": "ok", "zone_id": zone_id, "name": zone.name}

    def update_light_schedule(self, zone_id: str, start_time: time, stop_time: time) -> dict[str, object]:
        zone = self.get_zone(zone_id)
        if zone is None:
            raise ValueError(f"Unknown zone_id: {zone_id}")

        if not isinstance(start_time, time) or not isinstance(stop_time, time):
            raise ValueError("Light times must be valid Python time objects")

        zone.light_start_time = start_time
        zone.light_stop_time = stop_time

        return {
            "status": "ok",
            "zone_id": zone_id,
            "light_start_time": zone.light_start_time.isoformat(timespec="minutes"),
            "light_stop_time": zone.light_stop_time.isoformat(timespec="minutes"),
        }

    def set_led_range(self, zone_id: str, start_index: int, end_index: int) -> dict[str, object]:
        zone = self.get_zone(zone_id)
        if zone is None:
            raise ValueError(f"Unknown zone_id: {zone_id}")

        total_leds = max(settings.led_count, 1)
        safe_start = max(0, min(int(start_index), total_leds - 1))
        safe_end = max(safe_start, min(int(end_index), total_leds - 1))

        zone.led_start_index = safe_start
        zone.led_end_index = safe_end

        return {
            "status": "ok",
            "zone_id": zone_id,
            "led_start_index": zone.led_start_index,
            "led_end_index": zone.led_end_index,
        }

    def update_moisture_target(self, zone_id: str, moisture_target: float) -> dict[str, object]:
        zone = self.get_zone(zone_id)
        if zone is None:
            raise ValueError(f"Unknown zone_id: {zone_id}")

        clamped_target = max(0.0, min(float(moisture_target), 100.0))
        zone.moisture_target = round(clamped_target, 1)

        return {
            "status": "ok",
            "zone_id": zone_id,
            "moisture_target": zone.moisture_target,
        }
