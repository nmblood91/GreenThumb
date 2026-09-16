from __future__ import annotations

import logging
import struct

from greenthumb.models import SensorSample

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

import smbus2


class SoilSensorHub:
    """Reads moisture sensors for each plant zone via Adafruit STEMMA soil sensors using Seesaw protocol."""

    def __init__(self, addresses: list[int] | None = None) -> None:
        print(f"DEBUG: SoilSensorHub.__init__ called with addresses={addresses}", flush=True)
        self.addresses = addresses or [0x36, 0x37, 0x38, 0x39]
        self.bus: smbus2.SMBus | None = None
        self._initialized_sensors: set[int] = set()

        try:
            print(f"DEBUG: Opening I2C bus 1", flush=True)
            self.bus = smbus2.SMBus(1)  # Raspberry Pi I2C bus 1
            print(f"DEBUG: I2C bus opened, testing addresses: {self.addresses}", flush=True)
            for addr in self.addresses:
                try:
                    print(f"DEBUG: Testing sensor at 0x{addr:02x}", flush=True)
                    # Test connection by reading status
                    self._seesaw_read(addr, 0x00, 1)
                    self._initialized_sensors.add(addr)
                    print(f"DEBUG: Sensor at 0x{addr:02x} initialized successfully", flush=True)
                    logger.info(f"Initialized STEMMA sensor at 0x{addr:02x}")
                except Exception as e:
                    print(f"DEBUG: Failed to initialize sensor at 0x{addr:02x}: {e}", flush=True)
                    logger.warning(f"Failed to initialize sensor at 0x{addr:02x}: {e}")
        except Exception as e:
            print(f"DEBUG: Failed to initialize I2C bus: {e}", flush=True)
            logger.error(f"Failed to initialize I2C bus: {e}")

    def _seesaw_read(self, addr: int, register: int, length: int) -> bytes:
        """Read from Seesaw device register via I2C."""
        if not self.bus:
            raise RuntimeError("I2C bus not initialized")
        try:
            logger.debug(f"Reading from 0x{addr:02x} register 0x{register:02x} ({length} bytes)")
            # Send register address as single byte, then read response
            write = smbus2.i2c_msg.write(addr, [register])
            self.bus.i2c_rdwr(write)
            read = smbus2.i2c_msg.read(addr, length)
            self.bus.i2c_rdwr(read)
            result = bytes(read)
            logger.debug(f"Read result: {result.hex()}")
            return result
        except Exception as e:
            logger.error(f"I2C read error from 0x{addr:02x}: {e}", exc_info=True)
            raise

    def _seesaw_analog_read(self, addr: int, channel: int) -> int:
        """Read analog value from channel (0=moisture, 1=temperature)."""
        # ANALOG register is 0x0F, followed by channel number
        data = self._seesaw_read(addr, 0x0F, 2)
        # Convert 2-byte response to 16-bit unsigned int (big-endian)
        return struct.unpack(">H", data)[0]

    def read_all(self) -> list[SensorSample]:
        samples: list[SensorSample] = []
        for address in self.addresses:
            samples.append(self.read_one(address))
        return samples

    def read_one(self, address: int) -> SensorSample:
        if address not in self._initialized_sensors:
            logger.warning(f"Sensor at 0x{address:02x} not initialized; returning -1")
            return SensorSample(sensor_address=address, moisture_percent=-1.0, temperature_c=-1.0)

        try:
            # Read capacitive moisture (channel 0)
            moisture_raw = self._seesaw_analog_read(address, 0)
            # Read temperature (channel 1)
            temperature_raw = self._seesaw_analog_read(address, 1)
            # Temperature is returned as raw 16-bit value; STEMMA sensor returns value / 256
            temperature_c = temperature_raw / 256.0
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
