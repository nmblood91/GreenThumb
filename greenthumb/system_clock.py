"""Reading and setting the host clock.

The lighting schedule compares wall-clock times, so a planter in the wrong
timezone runs its photoperiod at the wrong hours and nothing looks broken. The
UI fixes that in one tap by sending the timezone the viewing device reports,
which is why this module exists.

Timezone only, never the time itself. `timedatectl set-time` refuses to run
while NTP is active, so offering it would mean switching NTP off and accepting
a clock that drifts and ignores DST -- worse than the problem being solved. Set
the zone, let NTP keep the time.
"""

from __future__ import annotations

import logging
import subprocess
import time
import zoneinfo
from datetime import datetime

logger = logging.getLogger(__name__)

TIMEDATECTL = "/usr/bin/timedatectl"
COMMAND_TIMEOUT = 10


def known_timezones() -> set[str]:
    """Zone names this host actually has, from its own tzdata."""
    try:
        return zoneinfo.available_timezones()
    except Exception as exc:  # pragma: no cover - only if tzdata is missing
        logger.warning("Could not list timezones: %s", exc)
        return set()


def _timedatectl_show() -> dict[str, str]:
    try:
        result = subprocess.run(
            [TIMEDATECTL, "show"],
            capture_output=True, text=True, timeout=COMMAND_TIMEOUT, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("timedatectl unavailable: %s", exc)
        return {}
    if result.returncode != 0:
        return {}
    values = {}
    for line in result.stdout.splitlines():
        key, _, value = line.partition("=")
        if key:
            values[key.strip()] = value.strip()
    return values


def status() -> dict[str, object]:
    """What the host believes the time and zone to be."""
    shown = _timedatectl_show()
    now = datetime.now().astimezone()
    return {
        "status": "ok",
        # ISO with offset, so the browser can render it without guessing.
        "now": now.isoformat(timespec="seconds"),
        "timezone": shown.get("Timezone") or time.tzname[0],
        "ntp_synchronised": shown.get("NTPSynchronized") == "yes",
        "ntp_service_active": shown.get("NTPService") == "active",
        # False where timedatectl is absent, so the UI can say the control
        # will not work here rather than failing on the button press.
        "can_set": bool(shown),
    }


def set_timezone(name: str) -> dict[str, object]:
    """Point the host at `name`, which must be a zone this host knows.

    Validated against the tz database rather than sanitised: the value arrives
    from a browser, and an allow-list of real zone names is the only check that
    cannot be talked around. The subprocess call passes a list, never a shell
    string, so there is no second layer to get wrong either.
    """
    candidate = (name or "").strip()
    if candidate not in known_timezones():
        raise ValueError(f"Unknown timezone: {name!r}")

    try:
        result = subprocess.run(
            ["sudo", "-n", TIMEDATECTL, "set-timezone", candidate],
            capture_output=True, text=True, timeout=COMMAND_TIMEOUT, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"Could not run timedatectl: {exc}") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or f"exit {result.returncode}"
        raise RuntimeError(f"Could not set the timezone: {detail}")

    # This process cached the old zone when it first asked the time, so
    # datetime.now() would keep answering in it until a restart without this.
    # Unix only -- absent on the Windows dev machine, where there is no
    # timedatectl to have succeeded in the first place.
    if hasattr(time, "tzset"):
        time.tzset()
    logger.info("System timezone set to %s", candidate)
    return status()
