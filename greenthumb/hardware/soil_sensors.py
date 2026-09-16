from __future__ import annotations

import logging

from greenthumb.models import SensorSample

logger = logging.getLogger(__name__)

import smbus2
from adafruit_seesaw import seesaw


class SoilSensorHub:
    """Reads moisture sensors for each plant zone via Adafruit STEMMA soil sensors."""

    def __init__(self, addresses: list[int] | None = None) -> None:
        self.addresses = addresses or [0x36, 0x37, 0x38, 0x39]
        self.bus: smbus2.SMBus | None = None
        self._sensors: dict[int, seesaw.Seesaw] = {}

        try:
            self.bus = smbus2.SMBus(1)  # Raspberry Pi I2C bus 1
            for addr in self.addresses:
                try:
                    self._sensors[addr] = seesaw.Seesaw(self.bus, addr=addr)
                    logger.info(f"Initialized STEMMA sensor at 0x{addr:02x}")
                except Exception as e:
                    logger.warning(f"Failed to initialize sensor at 0x{addr:02x}: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize I2C bus: {e}")

    def read_all(self) -> list[SensorSample]:
        samples: list[SensorSample] = []
        for address in self.addresses:
            samples.append(self.read_one(address))
        return samples

    def read_one(self, address: int) -> SensorSample:
        if address not in self._sensors:
            logger.warning(f"Sensor at 0x{address:02x} not initialized; returning -1")
            return SensorSample(sensor_address=address, moisture_percent=-1.0, temperature_c=-1.0)

        try:
            sensor = self._sensors[address]
            moisture_raw = sensor.analog_read(0)
            temperature_c = sensor.get_temp()
            return SensorSample(
                sensor_address=address,
                moisture_percent=float(moisture_raw),
                temperature_c=round(temperature_c, 1),
            )
        except Exception as e:
            logger.error(f"Error reading sensor at 0x{address:02x}: {e}")
            return SensorSample(sensor_address=address, moisture_percent=-1.0, temperature_c=-1.0)

    def __del__(self) -> None:
        if self.bus:
            try:
                self.bus.close()
            except Exception:
                pass


class SensorReadError(RuntimeError):
    """Raised when the sensing stack is unavailable."""
