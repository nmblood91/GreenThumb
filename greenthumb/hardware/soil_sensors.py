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


def unavailable_sample(address: int) -> SensorSample:
    """Reading for a sensor that is absent or failed; -1 never looks like real data."""
    return SensorSample(
        sensor_address=address,
        moisture_percent=-1.0,
        moisture_raw=-1.0,
        temperature_c=-1.0,
    )


class SoilSensorHub:
    """Reads Adafruit STEMMA soil sensors over I2C using the seesaw protocol."""

    def __init__(
        self,
        addresses: list[int] | None = None,
        raw_dry: int = 350,
        raw_wet: int = 1016,
    ) -> None:
        self.addresses = addresses or [0x36, 0x37, 0x38, 0x39]
        self.raw_dry = raw_dry
        self.raw_wet = raw_wet
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

    def raw_to_percent(self, raw: float) -> float:
        span = max(self.raw_wet - self.raw_dry, 1)
        percent = (raw - self.raw_dry) / span * 100.0
        return round(max(0.0, min(percent, 100.0)), 1)

    def read_all(self) -> list[SensorSample]:
        return [self.read_one(address) for address in self.addresses]

    def read_one(self, address: int) -> SensorSample:
        # Sensors get plugged in after startup, so re-probe addresses that have
        # not answered yet instead of writing them off until the next restart.
        if address not in self._initialized_sensors and not self._try_initialize(address):
            return unavailable_sample(address)

        try:
            moisture = self._read_moisture(address)
            temperature = self._read_temperature(address)
        except Exception as exc:
            logger.error("Error reading sensor at 0x%02x: %s", address, exc)
            # Forget it so the next poll re-probes; a reset often recovers a
            # sensor that dropped off, and this covers unplug/replug too.
            self._initialized_sensors.discard(address)
            return unavailable_sample(address)

        logger.debug("0x%02x moisture=%d temp=%.1fC", address, moisture, temperature)
        return SensorSample(
            sensor_address=address,
            moisture_percent=self.raw_to_percent(moisture),
            moisture_raw=float(moisture),
            temperature_c=round(temperature, 1),
        )

    def __del__(self) -> None:
        if self.bus:
            try:
                self.bus.close()
            except Exception:
                pass


def _soak(hub: SoilSensorHub, seconds: int, interval: float) -> int:
    """Hammer the bus and report per-address error rates.

    Intermittent I2C trouble from cable capacitance or noise shows up as
    occasional failed reads, which are invisible in a single sample and easy to
    mistake for a flaky sensor weeks later. This turns it into a number.
    """
    stats = {
        address: {"reads": 0, "errors": 0, "values": []} for address in hub.addresses
    }
    started = time.monotonic()
    deadline = started + seconds
    next_report = started + 10

    print(f"Soaking the I2C bus for {seconds}s across {len(hub.addresses)} addresses...")
    while time.monotonic() < deadline:
        for address in hub.addresses:
            sample = hub.read_one(address)
            entry = stats[address]
            entry["reads"] += 1
            if sample.moisture_raw < 0:
                entry["errors"] += 1
            else:
                entry["values"].append(sample.moisture_raw)

        now = time.monotonic()
        if now >= next_report:
            errors = sum(e["errors"] for e in stats.values())
            reads = sum(e["reads"] for e in stats.values())
            print(f"  {now - started:5.0f}s  {reads} reads, {errors} errors")
            next_report = now + 10
        time.sleep(interval)

    print(f"\n{'addr':<6} {'reads':>7} {'errors':>7} {'rate':>7}  {'raw min/mean/max':<22} verdict")
    worst = 0.0
    for address, entry in stats.items():
        reads, errors = entry["reads"], entry["errors"]
        values = entry["values"]
        rate = (errors / reads * 100) if reads else 0.0

        if not values:
            spread, verdict = "-", "no sensor at this address"
        else:
            spread = f"{min(values):.0f} / {sum(values) / len(values):.0f} / {max(values):.0f}"
            worst = max(worst, rate)
            if errors == 0:
                verdict = "clean"
            elif rate < 1:
                verdict = "occasional dropouts, acceptable"
            else:
                verdict = "unreliable - check routing, hub pull-ups, cable length"

        print(f"0x{address:02x}   {reads:>7} {errors:>7} {rate:>6.2f}%  {spread:<22} {verdict}")

    if worst == 0:
        print("\nNo errors. The bus is healthy at this cable length.")
    elif worst < 1:
        print(f"\nWorst address {worst:.2f}% errors. Tolerable, but watch it if cabling changes.")
    else:
        print(
            f"\nWorst address {worst:.2f}% errors. Try a slower I2C clock "
            "(dtparam=i2c_arm_baudrate), check the hubs for stacked pull-up "
            "resistors, and keep the run away from the LED data and motor wiring."
        )
    return 0 if worst < 1 else 1


if __name__ == "__main__":
    import argparse
    import sys

    from greenthumb.config import settings

    parser = argparse.ArgumentParser(description="Read the soil sensors directly.")
    parser.add_argument(
        "--soak",
        type=int,
        nargs="?",
        const=60,
        metavar="SECONDS",
        help="hammer the bus for this long (default 60s) and report error rates",
    )
    parser.add_argument(
        "--interval", type=float, default=0.2, help="seconds between soak passes"
    )
    args = parser.parse_args()

    # Per-read errors are the thing being counted during a soak, so logging each
    # one would bury the summary in exactly the case the summary is for.
    logging.basicConfig(
        level=logging.CRITICAL if args.soak else logging.DEBUG,
        format="%(levelname)s %(name)s: %(message)s",
    )

    hub = SoilSensorHub(
        addresses=settings.moisture_sensor_addresses_list,
        raw_dry=settings.moisture_raw_dry,
        raw_wet=settings.moisture_raw_wet,
    )

    if args.soak:
        sys.exit(_soak(hub, args.soak, args.interval))

    for sample in hub.read_all():
        print(
            f"0x{sample.sensor_address:02x}  raw={sample.moisture_raw:.0f}  "
            f"moisture={sample.moisture_percent}%  temp={sample.temperature_c}C"
        )
