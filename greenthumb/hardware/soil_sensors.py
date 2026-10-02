from __future__ import annotations

import logging
import statistics
import struct
import time
from datetime import datetime

import smbus2

from greenthumb import state
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
        calibration: dict[int, dict[str, int]] | None = None,
    ) -> None:
        self.addresses = addresses or [0x36, 0x37, 0x38, 0x39]
        self.raw_dry = raw_dry
        self.raw_wet = raw_wet
        # Per-address endpoints measured by --calibrate, overriding raw_dry and
        # raw_wet for the sensors that have them. Sensors read meaningfully
        # differently from each other in identical conditions, so one global
        # span puts that spread straight into the reported percentage.
        self.calibration = calibration or {}
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

    def endpoints_for(self, address: int | None) -> tuple[int, int]:
        """Calibrated dry/wet for one address, falling back per endpoint.

        Each endpoint falls back independently, because calibrating dry and
        calibrating wet are separate passes: a sensor with only its dry point
        measured should use that and the global default for wet, not revert
        both.
        """
        entry = self.calibration.get(address) if address is not None else None
        if not entry:
            return self.raw_dry, self.raw_wet
        return (
            int(entry.get("dry", self.raw_dry)),
            int(entry.get("wet", self.raw_wet)),
        )

    def raw_to_percent(self, raw: float, address: int | None = None) -> float:
        dry, wet = self.endpoints_for(address)
        span = max(wet - dry, 1)
        percent = (raw - dry) / span * 100.0
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
            moisture_percent=self.raw_to_percent(moisture, address),
            moisture_raw=float(moisture),
            temperature_c=round(temperature, 1),
        )

    def __del__(self) -> None:
        # getattr, not self.bus: if __init__ raised before setting it, __del__
        # still runs and an AttributeError here is unraisable noise that buries
        # the real error.
        if getattr(self, "bus", None):
            try:
                self.bus.close()
            except Exception:
                pass


def _collect(
    hub: SoilSensorHub,
    seconds: int,
    interval: float,
    progress: bool = True,
) -> dict[int, dict]:
    """Read every address repeatedly, returning per-address reads/errors/values.

    Shared by the soak test and by calibration: both want many samples per
    address over a fixed window, and differ only in what they do with them.
    """
    stats: dict[int, dict] = {
        address: {"reads": 0, "errors": 0, "values": []} for address in hub.addresses
    }
    started = time.monotonic()
    deadline = started + seconds
    next_report = started + 10

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
        if progress and now >= next_report:
            errors = sum(e["errors"] for e in stats.values())
            reads = sum(e["reads"] for e in stats.values())
            print(f"  {now - started:5.0f}s  {reads} reads, {errors} errors")
            next_report = now + 10
        time.sleep(interval)

    return stats


def _soak(hub: SoilSensorHub, seconds: int, interval: float) -> int:
    """Hammer the bus and report per-address error rates.

    Intermittent I2C trouble from cable capacitance or noise shows up as
    occasional failed reads, which are invisible in a single sample and easy to
    mistake for a flaky sensor weeks later. This turns it into a number.
    """
    print(f"Soaking the I2C bus for {seconds}s across {len(hub.addresses)} addresses...")
    stats = _collect(hub, seconds, interval)

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


# Below this, a measured wet point is not plausibly wetter than the dry point --
# almost always a prong that never reached the water, or a sensor still sitting
# in air. Writing it would make the zone read 100% permanently.
MIN_CALIBRATION_SPAN = 50

# A stable sensor in a uniform medium barely moves; yours held 6-13 counts in
# air. Much more than this and the reading had not settled, so the median is
# being taken over a moving target.
UNSTABLE_SPREAD = 40


def calibrate(
    hub: SoilSensorHub,
    endpoint: str,
    seconds: int = 20,
    interval: float = 0.2,
    state_path=None,
) -> dict[int, dict[str, object]]:
    """Sample every sensor and record one calibration endpoint for each.

    `endpoint` is "dry" (sensors in open air) or "wet" (prongs in water). The
    two are separate passes so either can be redone without losing the other.

    The median is used rather than the mean: it ignores a single outlier read,
    and with hundreds of samples there is no reason to be sensitive to one.
    """
    if endpoint not in ("dry", "wet"):
        raise ValueError(f"endpoint must be 'dry' or 'wet', not {endpoint!r}")

    existing = state.load_calibration(state_path)
    stats = _collect(hub, seconds, interval, progress=False)
    measured_at = datetime.utcnow().isoformat(timespec="seconds")

    results: dict[int, dict[str, object]] = {}
    for address, entry in stats.items():
        values = entry["values"]
        outcome: dict[str, object] = {
            "address": address,
            "reads": entry["reads"],
            "errors": entry["errors"],
        }

        if not values:
            outcome.update(written=False, reason="no sensor answered at this address")
            results[address] = outcome
            continue

        value = int(round(statistics.median(values)))
        spread = int(max(values) - min(values))
        outcome.update(value=value, spread=spread, samples=len(values))

        if spread > UNSTABLE_SPREAD:
            outcome.update(
                written=False,
                reason=(
                    f"readings moved {spread} counts during the run, so they had "
                    "not settled -- let the sensor sit and try again"
                ),
            )
            results[address] = outcome
            continue

        # Guard against the obvious operator error: running the wet pass with
        # the sensors still in air, or the dry pass with them still wet. Either
        # produces a span that makes the percentage meaningless.
        other = existing.get(address, {})
        if endpoint == "wet" and "dry" in other:
            if value - other["dry"] < MIN_CALIBRATION_SPAN:
                outcome.update(
                    written=False,
                    reason=(
                        f"wet reading {value} is not meaningfully above the dry "
                        f"point {other['dry']} -- are the prongs actually in water?"
                    ),
                )
                results[address] = outcome
                continue
        if endpoint == "dry" and "wet" in other:
            if other["wet"] - value < MIN_CALIBRATION_SPAN:
                outcome.update(
                    written=False,
                    reason=(
                        f"dry reading {value} is not meaningfully below the wet "
                        f"point {other['wet']} -- is the sensor dry and in air?"
                    ),
                )
                results[address] = outcome
                continue

        state.save_calibration_point(
            address,
            endpoint,
            value,
            samples=len(values),
            measured_at=measured_at,
            path=state_path,
        )
        outcome["written"] = True
        results[address] = outcome

    # Apply immediately so a running process reflects the new calibration
    # without a restart -- which is the whole point of persisting it.
    hub.calibration = state.load_calibration(state_path)
    return results


def _print_calibration(hub: SoilSensorHub, state_path=None) -> int:
    stored = state.load_calibration(state_path)
    print(f"{'addr':<6} {'dry':>6} {'wet':>6} {'span':>6}  source")
    for address in hub.addresses:
        entry = stored.get(address, {})
        dry, wet = hub.endpoints_for(address)
        if not entry:
            source = "global default"
        elif "dry" in entry and "wet" in entry:
            source = "calibrated"
        else:
            missing = "wet" if "dry" in entry else "dry"
            source = f"half calibrated, {missing} still default"
        print(f"0x{address:02x}  {dry:>6} {wet:>6} {wet - dry:>6}  {source}")
    if not stored:
        print(
            "\nNothing calibrated yet. Every sensor is using "
            "MOISTURE_RAW_DRY/MOISTURE_RAW_WET from .env."
        )
    return 0


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
    parser.add_argument(
        "--calibrate",
        choices=("dry", "wet"),
        help=(
            "record one calibration endpoint for every sensor. 'dry' with the "
            "sensors in open air, 'wet' with the prongs in water -- only the "
            "prongs, up to the marked line, these boards are not waterproof"
        ),
    )
    parser.add_argument(
        "--seconds",
        type=int,
        default=20,
        help="how long to sample during --calibrate (default 20s)",
    )
    parser.add_argument(
        "--show-calibration",
        action="store_true",
        help="print the stored calibration and exit",
    )
    args = parser.parse_args()

    # Per-read errors are the thing being counted during a soak, so logging each
    # one would bury the summary in exactly the case the summary is for. The
    # same applies to calibration, which reads just as hard.
    quiet = args.soak or args.calibrate
    logging.basicConfig(
        level=logging.CRITICAL if quiet else logging.DEBUG,
        format="%(levelname)s %(name)s: %(message)s",
    )

    hub = SoilSensorHub(
        addresses=settings.moisture_sensor_addresses_list,
        raw_dry=settings.moisture_raw_dry,
        raw_wet=settings.moisture_raw_wet,
        calibration=state.load_calibration(),
    )

    if args.show_calibration:
        sys.exit(_print_calibration(hub))

    if args.soak:
        sys.exit(_soak(hub, args.soak, args.interval))

    if args.calibrate:
        where = "in open air" if args.calibrate == "dry" else "with the prongs in water"
        print(
            f"Calibrating the {args.calibrate.upper()} point over {args.seconds}s. "
            f"All {len(hub.addresses)} sensors should be {where}."
        )
        if args.calibrate == "wet":
            print(
                "Only the prongs, up to the marked line -- these boards are not "
                "waterproof and the connector end must stay dry.\n"
            )
        results = calibrate(hub, args.calibrate, args.seconds, args.interval)

        print(f"\n{'addr':<6} {'value':>6} {'spread':>7} {'samples':>8}  result")
        failures = 0
        for address, outcome in results.items():
            if outcome.get("written"):
                print(
                    f"0x{address:02x}  {outcome['value']:>6} {outcome['spread']:>7} "
                    f"{outcome['samples']:>8}  stored as {args.calibrate}"
                )
            else:
                failures += 1
                value = outcome.get("value", "-")
                shown = f"{value:>6}" if value != "-" else f"{'-':>6}"
                print(f"0x{address:02x}  {shown} {'-':>7} {'-':>8}  NOT STORED: {outcome['reason']}")

        if failures:
            print(f"\n{failures} sensor(s) not stored. Fix the cause and re-run.")
        else:
            print("\nAll sensors stored. Run --show-calibration to review.")
        sys.exit(1 if failures else 0)

    for sample in hub.read_all():
        print(
            f"0x{sample.sensor_address:02x}  raw={sample.moisture_raw:.0f}  "
            f"moisture={sample.moisture_percent}%  temp={sample.temperature_c}C"
        )
