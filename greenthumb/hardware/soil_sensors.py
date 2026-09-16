from __future__ import annotations

import logging
import struct
import time

import smbus2

from greenthumb.models import SensorSample

logger = logging.getLogger(__name__)

I2C_BUS = 1

SEESAW_STATUS_BASE = 0x00
SEESAW_TOUCH_BASE = 0x0F

SEESAW_STATUS_HW_ID = 0x01
SEESAW_STATUS_TEMP = 0x04
SEESAW_STATUS_SWRST = 0x7F

SEESAW_TOUCH_CHANNEL_OFFSET = 0x10

# The soil sensor ships on a SAMD09; later seesaw boards report the tiny8x7 id.
VALID_HW_IDS = (0x55, 0x87)

MOISTURE_TOUCH_PIN = 0
NOT_READY = 0xFFFF


class SensorReadError(RuntimeError):
    """Raised when the sensing stack is unavailable."""


class SoilSensorHub:
    """Reads Adafruit STEMMA soil sensors over I2C using the seesaw protocol."""

    def __init__(self, addresses: list[int] | None = None) -> None:
        self.addresses = addresses or [0x36, 0x37, 0x38, 0x39]
        self.bus: smbus2.SMBus | None = None
        self._initialized_sensors: set[int] = set()

        try:
            self.bus = smbus2.SMBus(I2C_BUS)
        except Exception as exc:
            logger.error("Failed to open I2C bus %d: %s", I2C_BUS, exc)
            return

        for address in self.addresses:
            self._try_initialize(address)

    def _try_initialize(self, address: int) -> bool:
        try:
            self._reset(address)
            hw_id = self._read(address, SEESAW_STATUS_BASE, SEESAW_STATUS_HW_ID, 1)[0]
            if hw_id not in VALID_HW_IDS:
                raise SensorReadError(f"unexpected seesaw hardware id 0x{hw_id:02x}")
        except Exception as exc:
            logger.debug("No STEMMA sensor at 0x%02x: %s", address, exc)
            return False

        self._initialized_sensors.add(address)
        logger.info("Initialized STEMMA sensor at 0x%02x (hw id 0x%02x)", address, hw_id)
        return True

    def _write(self, address: int, base: int, function: int, payload: list[int] | None = None) -> None:
        if not self.bus:
            raise SensorReadError("I2C bus not initialized")
        message = smbus2.i2c_msg.write(address, [base, function, *(payload or [])])
        self.bus.i2c_rdwr(message)

    def _read(self, address: int, base: int, function: int, length: int, delay: float = 0.008) -> bytes:
        if not self.bus:
            raise SensorReadError("I2C bus not initialized")
        # Seesaw needs a STOP and a settling delay between the register write and
        # the read; a repeated start hands back stale bytes instead of the value.
        self._write(address, base, function)
        time.sleep(delay)
        message = smbus2.i2c_msg.read(address, length)
        self.bus.i2c_rdwr(message)
        return bytes(message)

    def _reset(self, address: int) -> None:
        self._write(address, SEESAW_STATUS_BASE, SEESAW_STATUS_SWRST, [0xFF])
        time.sleep(0.5)

    def _read_moisture(self, address: int) -> int:
        # The capacitive peripheral reports 0xFFFF until its conversion finishes,
        # so retry rather than surfacing the sentinel as a reading.
        for _ in range(10):
            raw = self._read(
                address,
                SEESAW_TOUCH_BASE,
                SEESAW_TOUCH_CHANNEL_OFFSET + MOISTURE_TOUCH_PIN,
                2,
                delay=0.005,
            )
            value = struct.unpack(">H", raw)[0]
            if value != NOT_READY:
                return value
            time.sleep(0.001)
        raise SensorReadError(f"moisture read at 0x{address:02x} never became ready")

    def _read_temperature(self, address: int) -> float:
        raw = bytearray(self._read(address, SEESAW_STATUS_BASE, SEESAW_STATUS_TEMP, 4, delay=0.005))
        raw[0] &= 0x3F  # high bits are status flags, not part of the fixed-point value
        return struct.unpack(">I", bytes(raw))[0] / 65536.0

    def read_all(self) -> list[SensorSample]:
        return [self.read_one(address) for address in self.addresses]

    def read_one(self, address: int) -> SensorSample:
        # Sensors get plugged in after startup, so re-probe addresses that have
        # not answered yet instead of writing them off until the next restart.
        if address not in self._initialized_sensors and not self._try_initialize(address):
            return SensorSample(sensor_address=address, moisture_percent=-1.0, temperature_c=-1.0)

        try:
            moisture = self._read_moisture(address)
            temperature = self._read_temperature(address)
        except Exception as exc:
            logger.error("Error reading sensor at 0x%02x: %s", address, exc)
            # Forget it so the next poll re-probes; a reset often recovers a
            # sensor that dropped off, and this covers unplug/replug too.
            self._initialized_sensors.discard(address)
            return SensorSample(sensor_address=address, moisture_percent=-1.0, temperature_c=-1.0)

        logger.debug("0x%02x moisture=%d temp=%.1fC", address, moisture, temperature)
        return SensorSample(
            sensor_address=address,
            moisture_percent=float(moisture),
            temperature_c=round(temperature, 1),
        )

    def __del__(self) -> None:
        if self.bus:
            try:
                self.bus.close()
            except Exception:
                pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    hub = SoilSensorHub()
    for sample in hub.read_all():
        print(
            f"0x{sample.sensor_address:02x}  moisture={sample.moisture_percent:.0f}  "
            f"temp={sample.temperature_c}C"
        )
