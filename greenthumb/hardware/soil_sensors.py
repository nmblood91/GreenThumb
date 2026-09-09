from __future__ import annotations

import random
from typing import Any

from greenthumb.models import SensorSample


class SoilSensorHub:
    """Reads moisture sensors for each plant zone. This is hardware-agnostic and can be swapped for SMBus or adafruit drivers."""

    def __init__(self, addresses: list[int] | None = None) -> None:
        self.addresses = addresses or [0x36, 0x37, 0x38, 0x39]

    def read_all(self) -> list[SensorSample]:
        samples: list[SensorSample] = []
        for address in self.addresses:
            samples.append(self.read_one(address))
        return samples

    def read_one(self, address: int) -> SensorSample:
        # Replace this with actual I2C reads when the Pi is connected to the sensor hub.
        simulated_moisture = 35 + (random.random() * 50)
        temperature = 22.0 + (random.random() * 4.0)
        return SensorSample(
            sensor_address=address,
            moisture_percent=round(simulated_moisture, 1),
            temperature_c=round(temperature, 1),
        )


class SensorReadError(RuntimeError):
    """Raised when the sensing stack is unavailable."""
