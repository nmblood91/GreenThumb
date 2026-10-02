import sys, types, json, tempfile
from pathlib import Path

sys.modules["smbus2"] = types.ModuleType("smbus2")  # no I2C on the laptop

from greenthumb import state
from greenthumb.hardware.soil_sensors import SoilSensorHub


def temp_path():
    return Path(tempfile.mkdtemp()) / "state.json"


# --- the store itself ---

p = temp_path()
assert state.load_state(p) == {}, "a missing file reads as empty, not an error"
print("ok: a missing state file is empty rather than fatal")

assert state.save_state({"zones": [{"zone_id": "zone_1", "name": "Fern"}]}, p)
assert state.load_state(p)["zones"][0]["name"] == "Fern"
assert state.load_state(p)["schema_version"] == state.SCHEMA_VERSION
print("ok: state round-trips and is stamped with a schema version")

p.write_text("{not json at all", encoding="utf-8")
assert state.load_state(p) == {}, "corrupt JSON must not raise"
print("ok: a corrupt state file degrades to defaults instead of crashing")

p.write_text('["a list, not an object"]', encoding="utf-8")
assert state.load_state(p) == {}, "wrong top-level type must not raise"
print("ok: a state file of the wrong shape is ignored")

# A write must leave no .tmp files behind, or they accumulate one per save.
p = temp_path()
for _ in range(3):
    state.save_state({"n": 1}, p)
strays = [f for f in p.parent.iterdir() if f.name != p.name]
assert not strays, f"temp files left behind: {strays}"
print("ok: atomic writes leave no stray temp files")


# --- calibration storage ---

p = temp_path()
assert state.load_calibration(p) == {}

state.save_calibration_point(0x36, "dry", 338, samples=474, path=p)
loaded = state.load_calibration(p)
assert loaded == {0x36: {"dry": 338}}, loaded
print("ok: one endpoint stores without inventing the other")

state.save_calibration_point(0x36, "wet", 700, path=p)
assert state.load_calibration(p)[0x36] == {"dry": 338, "wet": 700}
print("ok: the second endpoint merges rather than replacing the first")

raw = json.loads(p.read_text(encoding="utf-8"))
assert "0x36" in raw[state.CALIBRATION_KEY], raw
assert raw[state.CALIBRATION_KEY]["0x36"]["dry_samples"] == 474
print("ok: addresses are stored in readable hex with sample counts")

# Junk entries are skipped individually, not fatally.
raw[state.CALIBRATION_KEY]["not-an-address"] = {"dry": 1}
raw[state.CALIBRATION_KEY]["0x37"] = "not a dict"
raw[state.CALIBRATION_KEY]["0x38"] = {"dry": "banana", "wet": 900}
p.write_text(json.dumps(raw), encoding="utf-8")
loaded = state.load_calibration(p)
assert 0x36 in loaded and 0x37 not in loaded
assert loaded[0x38] == {"wet": 900}, loaded
print("ok: malformed calibration entries are skipped, good ones survive")

state.clear_calibration(p)
assert state.load_calibration(p) == {}
print("ok: calibration clears back to defaults")


# --- per-sensor conversion ---

hub = SoilSensorHub.__new__(SoilSensorHub)  # no I2C bus needed for the maths
hub.addresses = [0x36, 0x37]
hub.raw_dry, hub.raw_wet = 350, 1016
hub.calibration = {}

assert hub.endpoints_for(0x36) == (350, 1016)
assert hub.raw_to_percent(683, 0x36) == 50.0
print("ok: an uncalibrated sensor uses the global span")

hub.calibration = {0x36: {"dry": 300, "wet": 500}}
assert hub.endpoints_for(0x36) == (300, 500)
assert hub.raw_to_percent(400, 0x36) == 50.0
assert hub.endpoints_for(0x37) == (350, 1016), "other sensors keep the default"
print("ok: calibration applies per sensor, not globally")

# Two sensors reading the same raw value should report different percentages
# once calibrated differently -- that is the entire point of per-sensor.
hub.calibration = {0x36: {"dry": 320, "wet": 700}, 0x37: {"dry": 345, "wet": 700}}
assert hub.raw_to_percent(500, 0x36) != hub.raw_to_percent(500, 0x37)
print("ok: identical raw values differ once sensors are calibrated apart")

hub.calibration = {0x36: {"dry": 300}}
assert hub.endpoints_for(0x36) == (300, 1016), "wet falls back on its own"
hub.calibration = {0x36: {"wet": 800}}
assert hub.endpoints_for(0x36) == (350, 800), "dry falls back on its own"
print("ok: each endpoint falls back independently when half calibrated")

# A span of zero or backwards must not divide by zero or go negative.
hub.calibration = {0x36: {"dry": 500, "wet": 500}}
assert 0.0 <= hub.raw_to_percent(500, 0x36) <= 100.0
hub.calibration = {0x36: {"dry": 900, "wet": 100}}
assert 0.0 <= hub.raw_to_percent(500, 0x36) <= 100.0
print("ok: a zero or inverted span stays within 0-100 instead of exploding")

print("\nall state and calibration checks passed")
