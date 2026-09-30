import sys, types
sys.modules["smbus2"] = types.ModuleType("smbus2")

from greenthumb.config import settings
from greenthumb.models import SensorSample
from greenthumb.services.automation import GreenThumbAutomation

settings.auto_watering_enabled = True


class Hub:
    addresses = [0x36, 0x37, 0x38, 0x39]
    def raw_to_percent(self, raw): return 0.0
    def read_one(self, a): return SensorSample(a, 0.0, 350.0, 22.0)

class Pump:
    def __init__(self): self.calls = []; self.is_running = False
    def deliver_ml(self, v=100, **k): self.calls.append(v)

class Klip:
    def __init__(self, supply=True): self.supply = supply; self.moves = []
    def water_supply_present(self): return self.supply
    def move_gantry_absolute(self, p): self.moves.append(p); return {"ok": True}
    def status(self): return {"ok": True}

class Leds:
    mode = "schedule"
    def set_zone_segments(self, s): pass
    def status(self): return {"mode": "schedule"}


def temp_store():
    """Each suite gets its own database; tests must never touch the real one."""
    import tempfile
    from pathlib import Path
    from greenthumb.history import HistoryStore
    return HistoryStore(Path(tempfile.mkdtemp()) / "test.db")


def build(supply=True):
    pump, klip = Pump(), Klip(supply)
    return GreenThumbAutomation(Hub(), klip, pump, Leds(), history=temp_store()), pump, klip


# sensor off: never queried, watering unaffected
settings.water_sensor_enabled = False
auto, pump, klip = build(supply=False)
klip.water_supply_present = lambda: (_ for _ in ()).throw(AssertionError("queried while disabled"))
assert auto.water_zone("zone_1")["status"] == "ok"
assert pump.calls, "disabled sensor blocked watering"
print("ok: sensor disabled -> not queried, watering proceeds")

settings.water_sensor_enabled = True

# wet line waters
auto, pump, klip = build(supply=True)
assert auto.water_zone("zone_1")["status"] == "ok"
assert pump.calls == [100], pump.calls
print("ok: wet line waters normally")

# dry line blocks, and does not move the gantry
auto, pump, klip = build(supply=False)
result = auto.water_zone("zone_1")
assert result["status"] == "error", result
assert pump.calls == [], "pumped on a dry line"
assert klip.moves == [], "moved the gantry for a dose it could not give"
print("ok: dry line blocks the pump and the gantry move")

# unreadable sensor blocks too: declared present but silent is a fault
auto, pump, klip = build(supply=None)
assert auto.water_zone("zone_1")["status"] == "error"
assert pump.calls == []
print("ok: unreadable sensor blocks rather than pumping blind")

# a blocked dose must not consume the cooldown
auto, pump, klip = build(supply=False)
auto.water_zone("zone_1")
assert "zone_1" not in auto._last_watered, "blocked dose started a cooldown"
klip.supply = True
assert auto.water_zone("zone_1")["status"] == "ok"
assert pump.calls == [100], pump.calls
print("ok: blocked dose leaves the zone eligible to retry immediately")

# automatic loop is gated too
auto, pump, klip = build(supply=False)
for _ in range(12):
    auto.tick()
assert pump.calls == [], "control loop watered on a dry line"
print("ok: the control loop is gated, not just manual watering")

# transition logging: state tracked, not re-logged per tick
auto, pump, klip = build(supply=False)
auto.check_water_supply()
assert auto._supply_present is False
klip.supply = True
assert auto.check_water_supply() is True
assert auto._supply_present is True
print("ok: supply state transitions are tracked for change-only logging")

print("\nall supply-gate checks passed")
