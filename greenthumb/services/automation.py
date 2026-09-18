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


def within_window(now: time, start: time, stop: time) -> bool:
    if start <= stop:
        return start <= now < stop
    # A window that stops before it starts runs overnight, e.g. 20:00 to 06:00.
    return now >= start or now < stop


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
        self.leds = leds or LedController(
            led_count=settings.led_count,
            chip=settings.led_chip,
            color_order=settings.led_color_order,
            spi_bus=settings.led_spi_bus,
            spi_device=settings.led_spi_device,
        )

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
        self._supply_present: bool | None = None
        self._pump_timer: threading.Timer | None = None
        self._pump_lock_held = False

        self.zones = [
            ZoneSpec(name="Zone 1", zone_id="zone_1", sensor_address=0x36, moisture_target=45, watering_volume_ml=100, light_start_time=time(8, 0), light_stop_time=time(20, 0), position_mm=150),
            ZoneSpec(name="Zone 2", zone_id="zone_2", sensor_address=0x37, moisture_target=42, watering_volume_ml=100, light_start_time=time(8, 0), light_stop_time=time(20, 0), position_mm=400),
            ZoneSpec(name="Zone 3", zone_id="zone_3", sensor_address=0x38, moisture_target=48, watering_volume_ml=100, light_start_time=time(8, 0), light_stop_time=time(20, 0), position_mm=650),
            ZoneSpec(name="Zone 4", zone_id="zone_4", sensor_address=0x39, moisture_target=44, watering_volume_ml=100, light_start_time=time(8, 0), light_stop_time=time(20, 0), position_mm=900),
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
        # Lighting first and outside the lock: the strip is on its own SPI bus,
        # so it should keep following its schedule even while the gantry is busy.
        try:
            self._apply_lighting()
        except Exception:
            logger.exception("Failed to apply lighting schedule")

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

    def _apply_lighting(self) -> None:
        now = datetime.now().time()
        self.leds.set_zone_segments(
            [
                (
                    zone.led_start_index,
                    zone.led_end_index,
                    within_window(now, zone.light_start_time, zone.light_stop_time),
                )
                for zone in self.zones
            ]
        )

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
        # Once per tick rather than once per zone: the supply serves every zone,
        # so four identical queries and four identical warnings say nothing more
        # than one does.
        if settings.water_sensor_enabled and self.check_water_supply() is not True:
            return

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

    def run_pump(self) -> dict[str, object]:
        """Start the pump and leave it running, for bench testing.

        Not gated on the water sensor: running a dry line on purpose is part of
        what this is for.
        """
        # Held across requests rather than through _exclusive, so the control
        # loop cannot start a watering cycle while the pump is manually on.
        if not self._hardware_lock.acquire(blocking=False):
            raise HardwareBusyError("Pump run rejected: hardware is busy")
        self._pump_lock_held = True

        result = self.pump.start()
        if not result.get("ok", True) or not self.pump.is_running:
            # Release rather than strand the lock and block watering forever.
            self._release_pump_lock()
            return {"status": "error", "error": "pump did not start"}

        # Nothing else stops this if the browser closes or the network drops.
        self._pump_timer = threading.Timer(settings.pump_max_run_seconds, self._auto_stop_pump)
        self._pump_timer.daemon = True
        self._pump_timer.start()

        logger.info("Pump running, auto-stop in %ds", settings.pump_max_run_seconds)
        return {
            "status": "ok",
            "running": True,
            "max_run_seconds": settings.pump_max_run_seconds,
        }

    def stop_pump(self) -> dict[str, object]:
        """Stop the pump. Safe to call at any time, running or not."""
        if self._pump_timer:
            self._pump_timer.cancel()
            self._pump_timer = None

        self.pump.stop()
        self._release_pump_lock()
        return {"status": "ok", "running": False}

    def _auto_stop_pump(self) -> None:
        logger.warning("Pump hit its %ds limit, stopping", settings.pump_max_run_seconds)
        self.stop_pump()

    def _release_pump_lock(self) -> None:
        # Guarded: releasing a lock nobody holds would let the control loop and a
        # manual command run the hardware at the same time.
        if self._pump_lock_held:
            self._pump_lock_held = False
            self._hardware_lock.release()

    def check_water_supply(self) -> bool | None:
        """Wet/dry/unknown for the supply tube; None when no sensor is configured."""
        if not settings.water_sensor_enabled:
            return None

        present = self.klipper.water_supply_present()
        # Logged on change only: an empty reservoir would otherwise write a line
        # every tick, for every zone, for as long as it stayed empty.
        if present != self._supply_present:
            self._supply_present = present
            if present is True:
                logger.info("Water supply restored")
            elif present is False:
                logger.warning("Water supply is dry, watering is blocked")
            else:
                logger.warning("Water supply sensor unreadable, watering is blocked")
        return present

    def _move_and_water(self, zone: ZoneSpec, volume_ml: int | None = None) -> dict[str, object]:
        volume = zone.watering_volume_ml if volume_ml is None else max(0, int(volume_ml))

        # Checked before moving: no point travelling to a zone that cannot be
        # watered. Anything but a confirmed wet line blocks the pump.
        if settings.water_sensor_enabled and self.check_water_supply() is not True:
            # Debug, not warning: check_water_supply already logs the state
            # change, and the reason travels back to the caller in the response.
            reason = "water supply is dry or unreadable"
            logger.debug("Not watering %s: %s", zone.zone_id, reason)
            return {"status": "error", "zone_id": zone.zone_id, "error": reason}

        move = self.klipper.move_gantry_absolute(zone.position_mm)
        if not move.get("ok"):
            logger.warning(
                "Not watering %s: gantry move failed (%s)", zone.zone_id, move.get("error")
            )
            return {"status": "error", "zone_id": zone.zone_id, "error": move.get("error")}

        self.pump.deliver_ml(volume)
        self._last_watered[zone.zone_id] = datetime.now()
        return {"status": "ok", "zone_id": zone.zone_id, "volume_ml": volume}

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
            "lighting": self.leds.status(),
            "water_supply": {
                "enabled": settings.water_sensor_enabled,
                "present": self.check_water_supply(),
            },
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

    def water_zone(self, zone_id: str, volume_ml: int | None = None) -> dict[str, object]:
        zone = self.get_zone(zone_id)
        if zone is None:
            raise ValueError(f"Unknown zone_id: {zone_id}")

        # Moves first, like the automatic path. Pumping without moving waters
        # whatever the nozzle happens to be parked over.
        with self._exclusive(f"Watering {zone_id}"):
            return self._move_and_water(zone, volume_ml)

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

    def set_light_color_order(self, order: str) -> dict[str, object]:
        return self.leds.set_color_order(order)

    def set_light_chip(self, chip: str) -> dict[str, object]:
        return self.leds.set_chip(chip)

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

    def update_watering_volume(self, zone_id: str, volume_ml: int) -> dict[str, object]:
        zone = self.get_zone(zone_id)
        if zone is None:
            raise ValueError(f"Unknown zone_id: {zone_id}")

        zone.watering_volume_ml = max(0, int(volume_ml))
        return {
            "status": "ok",
            "zone_id": zone_id,
            "watering_volume_ml": zone.watering_volume_ml,
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
