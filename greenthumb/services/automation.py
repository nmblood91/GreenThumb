from __future__ import annotations

from datetime import datetime

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
            PlantSpec(name="Plant A", zone_id="zone_1", sensor_address=0x36, moisture_target=45.0, watering_volume_ml=180),
            PlantSpec(name="Plant B", zone_id="zone_2", sensor_address=0x37, moisture_target=42.0, watering_volume_ml=170),
            PlantSpec(name="Plant C", zone_id="zone_3", sensor_address=0x38, moisture_target=48.0, watering_volume_ml=190),
            PlantSpec(name="Plant D", zone_id="zone_4", sensor_address=0x39, moisture_target=44.0, watering_volume_ml=175),
        ]

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

    def home_motion_axis(self, axis: str) -> dict[str, object]:
        return self.klipper.home_axis(axis)
