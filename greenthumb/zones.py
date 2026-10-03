"""The zone set: which plant position each sensor address belongs to.

Kept here rather than inside `Automation.__init__` so that anything needing to
name a sensor can do so without constructing the whole service. An I2C address
is an implementation detail, and nobody who owns one of these should have to
recognise `0x38` as the third plant.

The zone set itself is defined by the code -- how many zones there are, and
which address each one reads. What the user may change is a zone's *name*, which
is persisted; `labels()` prefers a rename over the default here.
"""

from __future__ import annotations

from datetime import time

from greenthumb import state
from greenthumb.models import ZoneSpec


def default_zones() -> list[ZoneSpec]:
    """Fresh ZoneSpec instances, so callers cannot mutate a shared default."""
    return [
        ZoneSpec(name="Zone 1", zone_id="zone_1", sensor_address=0x36, moisture_target=45, watering_volume_ml=100, light_start_time=time(8, 0), light_stop_time=time(20, 0), position_mm=150),
        ZoneSpec(name="Zone 2", zone_id="zone_2", sensor_address=0x37, moisture_target=42, watering_volume_ml=100, light_start_time=time(8, 0), light_stop_time=time(20, 0), position_mm=400),
        ZoneSpec(name="Zone 3", zone_id="zone_3", sensor_address=0x38, moisture_target=48, watering_volume_ml=100, light_start_time=time(8, 0), light_stop_time=time(20, 0), position_mm=650),
        ZoneSpec(name="Zone 4", zone_id="zone_4", sensor_address=0x39, moisture_target=44, watering_volume_ml=100, light_start_time=time(8, 0), light_stop_time=time(20, 0), position_mm=900),
    ]


def names_by_address(state_path=None) -> dict[int, str]:
    """Address to zone name, preferring a name the user has saved."""
    names = {zone.sensor_address: zone.name for zone in default_zones()}

    by_id = {zone.zone_id: zone.sensor_address for zone in default_zones()}
    for saved in state.load_state(state_path).get("zones", []) or []:
        if not isinstance(saved, dict):
            continue
        address = by_id.get(str(saved.get("zone_id", "")))
        name = saved.get("name")
        if address is not None and isinstance(name, str) and name.strip():
            names[address] = name.strip()
    return names


def label_for(
    address: int,
    names: dict[int, str] | None = None,
    state_path=None,
) -> str:
    """"Zone 1 (0x36)", or just the address if it belongs to no zone.

    Both halves on purpose: the name is what the owner recognises, and the
    address is what they would read off a sensor or type into `i2cdetect` when
    something needs tracing.

    Pass `names` when labelling several addresses at once. Without it each call
    reads the state file, which is fine for printing a four-row table and not
    fine in a loop that runs per reading.
    """
    if names is None:
        names = names_by_address(state_path)
    name = names.get(address)
    return f"{name} (0x{address:02x})" if name else f"0x{address:02x}"
