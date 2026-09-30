from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path

from greenthumb.models import SensorSample

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "greenthumb.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    id               INTEGER PRIMARY KEY,
    recorded_at      INTEGER NOT NULL,
    sensor_address   INTEGER NOT NULL,
    moisture_raw     REAL NOT NULL,
    moisture_percent REAL NOT NULL,
    temperature_c    REAL
);
CREATE INDEX IF NOT EXISTS idx_readings_addr_time
    ON readings(sensor_address, recorded_at);

CREATE TABLE IF NOT EXISTS waterings (
    id          INTEGER PRIMARY KEY,
    recorded_at INTEGER NOT NULL,
    zone_id     TEXT NOT NULL,
    volume_ml   INTEGER NOT NULL,
    trigger     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_waterings_time ON waterings(recorded_at);
"""

# Enough points to show shape without sending 129,600 of them for a 90 day range.
TARGET_POINTS = 500
MINUTE = 60


def bucket_seconds_for(hours: float) -> int:
    """Time bucket that keeps a range near TARGET_POINTS samples per series."""
    if hours <= 6:
        return MINUTE
    if hours <= 48:
        return 5 * MINUTE
    if hours <= 24 * 7:
        return 30 * MINUTE
    return 6 * 60 * MINUTE


class HistoryStore:
    """Stores sensor readings and waterings in SQLite for the history chart."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # The control loop writes from an APScheduler thread while API reads come
        # from FastAPI's threadpool, so the connection is shared and every access
        # goes through the lock.
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        # WAL lets reads proceed during a write; NORMAL keeps this crash-safe
        # while only risking the last transaction on a power cut, which for
        # telemetry is worth the reduction in SD card wear.
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.executescript(SCHEMA)
        self._db.commit()
        logger.info("History database ready at %s", self.path)

    def record_readings(self, samples: list[SensorSample], at: int | None = None) -> int:
        """Store one tick's readings. Returns how many were kept."""
        timestamp = int(time.time()) if at is None else at
        rows = [
            (timestamp, s.sensor_address, s.moisture_raw, s.moisture_percent, s.temperature_c)
            # A failed or absent sensor reads -1, which would drag the chart to
            # the floor and poison every bucket average it landed in.
            for s in samples
            if s.moisture_raw >= 0
        ]
        if not rows:
            return 0

        # One transaction for the whole tick rather than one per sensor.
        with self._lock:
            self._db.executemany(
                "INSERT INTO readings"
                " (recorded_at, sensor_address, moisture_raw, moisture_percent, temperature_c)"
                " VALUES (?, ?, ?, ?, ?)",
                rows,
            )
            self._db.commit()
        return len(rows)

    def record_watering(
        self, zone_id: str, volume_ml: int, trigger: str, at: int | None = None
    ) -> None:
        timestamp = int(time.time()) if at is None else at
        with self._lock:
            self._db.execute(
                "INSERT INTO waterings (recorded_at, zone_id, volume_ml, trigger)"
                " VALUES (?, ?, ?, ?)",
                (timestamp, zone_id, int(volume_ml), trigger),
            )
            self._db.commit()

    def series(
        self, addresses: list[int], hours: float, now: int | None = None
    ) -> tuple[int, list[int], dict[int, dict[str, list[float | None]]]]:
        """Bucketed readings per address, aligned onto one shared timestamp axis.

        uPlot needs a single x array shared by every series, so the alignment
        happens here rather than being reimplemented in the browser. A None means
        that address had no reading in that bucket, which is real information --
        the sensor was unreadable.
        """
        bucket = bucket_seconds_for(hours)
        end = int(time.time()) if now is None else now
        since = end - int(hours * 3600)

        with self._lock:
            rows = self._db.execute(
                "SELECT sensor_address,"
                "       (recorded_at / ?) * ? AS bucket,"
                "       AVG(moisture_percent) AS moisture_percent,"
                "       AVG(temperature_c) AS temperature_c"
                " FROM readings"
                " WHERE recorded_at >= ?"
                " GROUP BY sensor_address, bucket"
                " ORDER BY bucket",
                (bucket, bucket, since),
            ).fetchall()

        by_address: dict[int, dict[int, sqlite3.Row]] = {}
        stamps: set[int] = set()
        for row in rows:
            by_address.setdefault(row["sensor_address"], {})[row["bucket"]] = row
            stamps.add(row["bucket"])

        timestamps = sorted(stamps)
        series: dict[int, dict[str, list[float | None]]] = {}
        for address in addresses:
            buckets = by_address.get(address, {})
            series[address] = {
                "moisture_percent": [
                    round(buckets[t]["moisture_percent"], 1) if t in buckets else None
                    for t in timestamps
                ],
                "temperature_c": [
                    round(buckets[t]["temperature_c"], 1)
                    if t in buckets and buckets[t]["temperature_c"] is not None
                    else None
                    for t in timestamps
                ],
            }
        return bucket, timestamps, series

    def waterings(self, hours: float, now: int | None = None) -> list[dict[str, object]]:
        end = int(time.time()) if now is None else now
        since = end - int(hours * 3600)
        with self._lock:
            rows = self._db.execute(
                "SELECT recorded_at, zone_id, volume_ml, trigger FROM waterings"
                " WHERE recorded_at >= ? ORDER BY recorded_at",
                (since,),
            ).fetchall()
        return [
            {
                "t": row["recorded_at"],
                "zone_id": row["zone_id"],
                "volume_ml": row["volume_ml"],
                "trigger": row["trigger"],
            }
            for row in rows
        ]

    def prune(self, retention_days: int, now: int | None = None) -> int:
        """Drop rows past the retention window. Returns rows deleted."""
        end = int(time.time()) if now is None else now
        cutoff = end - retention_days * 24 * 3600
        with self._lock:
            # DELETE does not shrink the file, but SQLite reuses the freed pages
            # and steady state is only tens of megabytes, so no VACUUM.
            readings = self._db.execute(
                "DELETE FROM readings WHERE recorded_at < ?", (cutoff,)
            ).rowcount
            waterings = self._db.execute(
                "DELETE FROM waterings WHERE recorded_at < ?", (cutoff,)
            ).rowcount
            self._db.commit()

        deleted = readings + waterings
        if deleted:
            logger.info("Pruned %d rows older than %d days", deleted, retention_days)
        return deleted

    def close(self) -> None:
        with self._lock:
            self._db.close()
