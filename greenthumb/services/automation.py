from __future__ import annotations

from datetime import datetime, time

from greenthumb.config import settings
from greenthumb.hardware.klipper_client import KlipperClient
from greenthumb.hardware.lighting import LedController
from greenthumb.hardware.pump import PumpController
from greenthumb.hardware.soil_sensors import SoilSensorHub
from greenthumb.models import PlantSpec, ZoneStatus


class GreenThumbAutomation:
    """Application service that coordinates sensors, watering, lighting, and movement."""

    def __init__(
        self,
        sensor_hub: SoilSensorHub | None = None,
        klipper_client: KlipperClient | None = None,
        pump: PumpController | None = None,
        leds: LedController | None = None,
    ) -> None:
        self.sensor_hub = sensor_hub or SoilSensorHub(addresses=settings.moisture_sensor_addresses)
        self.klipper = klipper_client or KlipperClient(settings.klipper_host)
        self.pump = pump or PumpController(pin=settings.pump_pin)
        self.leds = leds or LedController(led_count=settings.led_count)

        self.plants = [
            PlantSpec(name="Plant A", zone_id="zone_1", sensor_address=0x36, moisture_target=45, watering_volume_ml=180, light_start_time=time(8, 0), light_stop_time=time(20, 0), position_mm=150),
            PlantSpec(name="Plant B", zone_id="zone_2", sensor_address=0x37, moisture_target=42, watering_volume_ml=170, light_start_time=time(8, 0), light_stop_time=time(20, 0), position_mm=400),
            PlantSpec(name="Plant C", zone_id="zone_3", sensor_address=0x38, moisture_target=48, watering_volume_ml=190, light_start_time=time(8, 0), light_stop_time=time(20, 0), position_mm=650),
            PlantSpec(name="Plant D", zone_id="zone_4", sensor_address=0x39, moisture_target=44, watering_volume_ml=175, light_start_time=time(8, 0), light_stop_time=time(20, 0), position_mm=900),
        ]
        self.apply_default_led_ranges()

    def apply_default_led_ranges(self) -> None:
        plant_count = len(self.plants)
        if plant_count == 0:
            return

        total_leds = max(settings.led_count, 1)
        segment_length = total_leds // plant_count
        remainder = total_leds % plant_count

        start_index = 0
        for index, plant in enumerate(self.plants):
            segment_size = segment_length + (1 if index < remainder else 0)
            plant.led_start_index = start_index
            plant.led_end_index = start_index + segment_size - 1
            start_index += segment_size

        if self.plants:
            self.plants[-1].led_end_index = total_leds - 1

    def apply_default_zone_positions(self) -> None:
        if not self.plants:
            return

        rail_length = max(float(settings.gantry_rail_length_mm), 1.0)
        margin = max(float(settings.gantry_position_margin_mm), 0.0)
        usable_length = max(rail_length - (margin * 2), 1.0)
        plant_count = len(self.plants)

        for index, plant in enumerate(self.plants):
            ratio = (index + 1) / (plant_count + 1)
            plant.position_mm = round(margin + (usable_length * ratio), 1)

    def get_zone_positions(self) -> list[dict[str, object]]:
        return [{
            "zone_id": plant.zone_id,
            "name": plant.name,
            "position_mm": plant.position_mm,
        } for plant in self.plants]

    def set_zone_position(self, zone_id: str, position_mm: float) -> dict[str, object]:
        plant = next((item for item in self.plants if item.zone_id == zone_id), None)
        if plant is None:
            raise ValueError(f"Unknown zone_id: {zone_id}")

        max_position = settings.gantry_rail_length_mm
        bounded_position = max(0.0, min(float(position_mm), max_position))
        plant.position_mm = round(bounded_position, 1)

        return {
            "status": "ok",
            "zone_id": zone_id,
            "position_mm": plant.position_mm,
        }

    def get_overview(self) -> dict[str, object]:
        samples = self.sensor_hub.read_all()
        zone_status = []
        for spec in self.plants:
            sample = next((item for item in samples if item.sensor_address == spec.sensor_address), samples[0])
            zone_status.append(
                ZoneStatus(
                    zone_id=spec.zone_id,
                    moisture_percent=sample.moisture_percent,
                    target_moisture=spec.moisture_target,
                    pump_active=self.pump.is_running,
                    lighting_mode=self.leds.mode,
                    last_watered=datetime.utcnow().isoformat(timespec="seconds"),
                )
            )

        return {
            "app": settings.app_name,
            "movement": self.klipper.status(),
            "zones": [status.__dict__ for status in zone_status],
        }

    def read_sensors(self) -> list[dict[str, object]]:
        return [sample.__dict__ for sample in self.sensor_hub.read_all()]

    def water_zone(self, zone_id: str, volume_ml: int = 180) -> dict[str, object]:
        self.pump.deliver_ml(volume_ml)
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
        return self.klipper.home_axis(axis)

    def home_gantry(self) -> dict[str, object]:
        return self.klipper.home_gantry()

    def move_axis_relative(self, x_mm: float = 0.0, y_mm: float = 0.0, z_mm: float = 0.0) -> dict[str, object]:
        return self.klipper.move_relative(x_mm=x_mm, y_mm=y_mm, z_mm=z_mm)

    def move_gantry_relative(self, distance_mm: float) -> dict[str, object]:
        return self.klipper.move_gantry_relative(distance_mm)

    def move_to_zone(self, zone_id: str) -> dict[str, object]:
        plant = next((item for item in self.plants if item.zone_id == zone_id), None)
        if plant is None:
            raise ValueError(f"Unknown zone_id: {zone_id}")

        return self.move_gantry_relative(plant.position_mm)

    def get_plant(self, zone_id: str) -> PlantSpec | None:
        return next((plant for plant in self.plants if plant.zone_id == zone_id), None)

    def update_plant_name(self, zone_id: str, name: str) -> dict[str, object]:
        plant = self.get_plant(zone_id)
        if plant is None:
            raise ValueError(f"Unknown zone_id: {zone_id}")
        plant.name = name.strip() or plant.name
        return {"status": "ok", "zone_id": zone_id, "name": plant.name}

    def update_light_schedule(self, zone_id: str, start_time: time, stop_time: time) -> dict[str, object]:
        plant = self.get_plant(zone_id)
        if plant is None:
            raise ValueError(f"Unknown zone_id: {zone_id}")

        if not isinstance(start_time, time) or not isinstance(stop_time, time):
            raise ValueError("Light times must be valid Python time objects")

        plant.light_start_time = start_time
        plant.light_stop_time = stop_time

        return {
            "status": "ok",
            "zone_id": zone_id,
            "light_start_time": plant.light_start_time.isoformat(timespec="minutes"),
            "light_stop_time": plant.light_stop_time.isoformat(timespec="minutes"),
        }

    def set_led_range(self, zone_id: str, start_index: int, end_index: int) -> dict[str, object]:
        plant = self.get_plant(zone_id)
        if plant is None:
            raise ValueError(f"Unknown zone_id: {zone_id}")

        total_leds = max(settings.led_count, 1)
        safe_start = max(0, min(int(start_index), total_leds - 1))
        safe_end = max(safe_start, min(int(end_index), total_leds - 1))

        plant.led_start_index = safe_start
        plant.led_end_index = safe_end

        return {
            "status": "ok",
            "zone_id": zone_id,
            "led_start_index": plant.led_start_index,
            "led_end_index": plant.led_end_index,
        }

    def update_moisture_target(self, zone_id: str, moisture_target: float) -> dict[str, object]:
        plant = self.get_plant(zone_id)
        if plant is None:
            raise ValueError(f"Unknown zone_id: {zone_id}")

        clamped_target = max(0.0, min(float(moisture_target), 100.0))
        plant.moisture_target = round(clamped_target, 1)

        return {
            "status": "ok",
            "zone_id": zone_id,
            "moisture_target": plant.moisture_target,
        }
