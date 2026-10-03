import sys, types

sys.modules["smbus2"] = types.ModuleType("smbus2")  # no I2C on the laptop

from greenthumb import system_clock

calls = []


def fake_run(cmd, **kwargs):
    calls.append(cmd)
    return types.SimpleNamespace(returncode=0, stdout="", stderr="")


system_clock.subprocess.run = fake_run

# --- the value arrives from a browser, so it is an allow-list or nothing ---

hostile = [
    "America/Chicago; rm -rf /",
    "America/Chicago && reboot",
    "$(reboot)",
    "`reboot`",
    "../../etc/passwd",
    "Mars/Olympus_Mons",
    "",
    "   ",
]
for value in hostile:
    calls.clear()
    try:
        system_clock.set_timezone(value)
    except ValueError:
        assert not calls, f"ran a command for rejected input {value!r}: {calls}"
    else:
        raise AssertionError(f"accepted {value!r}")
print(f"ok: {len(hostile)} malformed or hostile zone names rejected before any command runs")

# A real zone is accepted and passed as list arguments, never a shell string.
calls.clear()
system_clock.set_timezone("America/Chicago")
# Two commands: the set, then a status read so the caller gets the new state.
cmd = calls[0]
assert isinstance(cmd, list), "must not be a shell string"
assert cmd[-2:] == ["set-timezone", "America/Chicago"], cmd
assert "-n" in cmd, "sudo must not block waiting for a password"
assert calls[1][-1] == "show", calls
print("ok: a real zone runs timedatectl with list arguments and non-interactive sudo")

# Surrounding whitespace is forgiven rather than rejected.
calls.clear()
system_clock.set_timezone("  Europe/London  ")
assert calls[0][-1] == "Europe/London", calls
print("ok: surrounding whitespace is trimmed")

# A refusal from timedatectl surfaces as an error, not a silent success.
def failing_run(cmd, **kwargs):
    return types.SimpleNamespace(returncode=1, stdout="", stderr="Access denied")


system_clock.subprocess.run = failing_run
try:
    system_clock.set_timezone("America/Chicago")
except RuntimeError as exc:
    assert "Access denied" in str(exc), exc
    print("ok: a refusal from timedatectl is reported, with its reason")
else:
    raise AssertionError("a failing timedatectl looked like success")

# A host without timedatectl reports that it cannot set the zone, rather than
# offering a button that cannot work.
def missing_run(cmd, **kwargs):
    raise FileNotFoundError("no timedatectl here")


system_clock.subprocess.run = missing_run
state = system_clock.status()
assert state["can_set"] is False, state
assert state["now"] and state["timezone"], state
print("ok: a host without timedatectl still reports a time, and can_set is False")

print("\nall system clock checks passed")
