"""Read-only SQLite logger for duoplasmatron GUI measurements.

This module is intentionally observer-only. It snapshots attributes that the
existing GUI/readout loop has already populated and writes them on a background
thread. It must not call hardware methods, get_data(), setters, update_ui(), or
switchOff().
"""

from __future__ import annotations

import argparse
import atexit
import datetime as _datetime
import hashlib
import json
import math
import os
import queue
import random
import shutil
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 3
CONFIG_PATH = Path(__file__).resolve().with_name("duo_logging_config.json")
TRUE_VALUES = {"1", "true", "yes"}

# event.event_type values (documented in PROJECT_GUIDE.md, "Parameter-change
# events"). "Observed" types are derived by the writer thread from consecutive
# cycle snapshots (one per ~1.4 s cycle); "requested" types are queued from the
# GUI main thread at the moment of the action.
EVENT_RUN_START_SNAPSHOT = "run_start_snapshot"  # observed: baseline controls
EVENT_SETPOINT_CHANGE = "setpoint_change"        # observed: control value changed
EVENT_CONTROL_MISSING = "control_missing"        # observed: value -> None/absent
EVENT_CONTROL_RESTORED = "control_restored"      # observed: None/absent -> value
EVENT_ITEM_ENABLED = "item_enabled"              # observed: enabled 0 -> 1
EVENT_ITEM_DISABLED = "item_disabled"            # observed: enabled 1 -> 0
EVENT_SETPOINT_REQUEST = "setpoint_request"      # requested: on_change_ctrl_proc
EVENT_PRESET_LOADED = "preset_loaded"            # requested: Presets menu


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS run (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    started_utc TEXT NOT NULL,
    started_unix REAL NOT NULL,
    hostname TEXT,
    pid INTEGER,
    app_title TEXT,
    db_path TEXT,
    db_schema_version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS signal (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    item_name TEXT NOT NULL,
    signal_name TEXT NOT NULL,
    signal_kind TEXT NOT NULL,
    channel_index INTEGER,
    unit TEXT,
    metadata_json TEXT,
    UNIQUE(source, item_name, signal_name, signal_kind, channel_index)
);

CREATE TABLE IF NOT EXISTS cycle (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL,
    cycle_index INTEGER NOT NULL,
    ts_utc TEXT NOT NULL,
    ts_unix REAL NOT NULL,
    monotonic_s REAL NOT NULL,
    FOREIGN KEY(run_id) REFERENCES run(id)
);

CREATE TABLE IF NOT EXISTS measurement (
    cycle_id INTEGER NOT NULL,
    signal_id INTEGER NOT NULL,
    value REAL,
    band_min REAL,
    band_max REAL,
    value_text TEXT,
    status TEXT,
    FOREIGN KEY(cycle_id) REFERENCES cycle(id),
    FOREIGN KEY(signal_id) REFERENCES signal(id)
);

CREATE INDEX IF NOT EXISTS idx_cycle_run_ts ON cycle(run_id, ts_unix);
CREATE INDEX IF NOT EXISTS idx_measurement_signal ON measurement(signal_id);
CREATE INDEX IF NOT EXISTS idx_measurement_cycle ON measurement(cycle_id);

CREATE TABLE IF NOT EXISTS event (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL,
    ts_utc TEXT NOT NULL,
    ts_unix REAL NOT NULL,
    event_type TEXT NOT NULL,
    item_name TEXT,
    signal_name TEXT,
    value_before TEXT,
    value_after TEXT,
    details_json TEXT,
    FOREIGN KEY(run_id) REFERENCES run(id)
);

CREATE TABLE IF NOT EXISTS note (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL,
    ts_utc TEXT NOT NULL,
    ts_unix REAL NOT NULL,
    cycle_index INTEGER,
    source TEXT,
    text TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES run(id)
);

CREATE INDEX IF NOT EXISTS idx_note_ts ON note(ts_unix);
"""

# Schema version 3 additions. Applied after SCHEMA_SQL every time a DB file is
# opened (including at monthly rotation), each step separately guarded so a
# failure never stops cycle logging. Old files just gain the new columns and
# tables; existing columns are never changed.
ADDITIVE_COLUMNS = (
    ("run", "run_uuid", "TEXT"),
    ("run", "stop_utc", "TEXT"),
    ("run", "config_hash", "TEXT"),
    ("run", "continued_from_rotation", "INTEGER NOT NULL DEFAULT 0"),
    ("event", "ts_mono", "REAL"),
)

ADDITIVE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS cycle_timing (
    cycle_id INTEGER PRIMARY KEY,
    loop_dt REAL,
    FOREIGN KEY(cycle_id) REFERENCES cycle(id)
);

CREATE INDEX IF NOT EXISTS idx_event_ts_utc ON event(ts_utc);
CREATE INDEX IF NOT EXISTS idx_event_signal ON event(item_name, signal_name);
"""

# Will likely add/change some dataclasses after discussing more with Bart and Petko, began with adding the easy to acess stuff


@dataclass(frozen=True)
class MeasurementRecord:
    item_name: str
    signal_name: str
    signal_kind: str
    channel_index: int | None
    unit: str | None
    metadata_json: str | None
    value: float | None
    band_min: float | None
    band_max: float | None
    value_text: str | None
    status: str | None


def _changed_beyond_tolerance(before: float, after: float) -> bool:
    return abs(after - before) > max(1e-9, 1e-6 * abs(before))


class ControlChangeTracker:
    """Derives observed parameter-change events from consecutive snapshots.

    Pure bookkeeping on already-copied MeasurementRecords: it touches no live
    item, widget or hardware object. Owned by the writer thread.
    """

    def __init__(self, source: str = "") -> None:
        self.source = source
        # key -> (value or None, status, cycle_index last seen, signal_id)
        self._prev: dict[tuple[Any, ...], tuple[Any, ...]] | None = None
        # item_name -> (enabled value or None, cycle_index)
        self._prev_enabled: dict[str, tuple[Any, ...]] = {}
        # key -> (consecutive_changes, ramp_start_value, snapshot seq of last change)
        self._runs: dict[tuple[Any, ...], tuple[Any, ...]] = {}
        self._seq = 0  # snapshots processed; "consecutive" means adjacent snapshots

    def key(self, rec: MeasurementRecord) -> tuple[Any, ...]:
        # identical to the signal table's UNIQUE key (see _signal_id)
        channel_index = -1 if rec.channel_index is None else rec.channel_index
        return (self.source, rec.item_name, rec.signal_name,
                rec.signal_kind, channel_index)

    def process(self, snapshot: dict[str, Any], signal_id: Any = None) -> list[dict[str, Any]]:
        """Return event dicts (same shape as log_event's) for this snapshot.

        signal_id is an optional callable rec -> signal.id.
        """
        self._seq += 1
        cycle_index = snapshot["cycle_index"]
        ts_unix = snapshot["ts_unix"]
        ts_utc = snapshot["ts_utc"]
        ts_mono = snapshot.get("monotonic_s")
        controls: dict[tuple[Any, ...], tuple[MeasurementRecord, Any]] = {}
        enabled: dict[str, MeasurementRecord] = {}
        for rec in snapshot["measurements"]:
            if rec.signal_kind == "control":
                sid = signal_id(rec) if signal_id is not None else None
                controls[self.key(rec)] = (rec, sid)
            elif rec.signal_kind == "item_attr" and rec.signal_name == "enabled":
                enabled[rec.item_name] = rec

        def event(event_type: str, item_name: Any, signal_name: Any,
                  before: Any, after: Any, details: dict[str, Any]) -> dict[str, Any]:
            return {
                "ts_utc": ts_utc,
                "ts_unix": ts_unix,
                "ts_mono": ts_mono,
                "event_type": event_type,
                "item_name": item_name,
                "signal_name": signal_name,
                "value_before": None if before is None else str(before),
                "value_after": None if after is None else str(after),
                "details_json": json.dumps(details, sort_keys=True, default=str),
            }

        events: list[dict[str, Any]] = []
        if self._prev is None:
            events.append(event(
                EVENT_RUN_START_SNAPSHOT, None, None, None, None, {
                    "cycle_index": cycle_index,
                    "controls": [
                        {"item_name": rec.item_name, "signal_name": rec.signal_name,
                         "channel_index": rec.channel_index, "signal_id": sid,
                         "value": rec.value, "status": rec.status}
                        for rec, sid in controls.values()],
                    "enabled": {name: rec.value for name, rec in enabled.items()},
                }))
            self._prev = {}
        else:
            for key, (rec, sid) in controls.items():
                prev = self._prev.get(key)
                before = None if prev is None else prev[0]
                details = {
                    "cycle_index": cycle_index,
                    "signal_id": sid,
                    "prev_cycle_index": None if prev is None else prev[2],
                }
                if before is not None and rec.value is not None:
                    if _changed_beyond_tolerance(before, rec.value):
                        run = self._runs.get(key)
                        if run is not None and run[2] == self._seq - 1:
                            run = (run[0] + 1, run[1], self._seq)
                        else:
                            run = (1, before, self._seq)
                        self._runs[key] = run
                        details["consecutive_changes"] = run[0]
                        if run[0] >= 2:
                            details["ramp_start_value"] = run[1]
                        events.append(event(
                            EVENT_SETPOINT_CHANGE, rec.item_name, rec.signal_name,
                            before, rec.value, details))
                elif before is not None:
                    details["status"] = rec.status
                    events.append(event(
                        EVENT_CONTROL_MISSING, rec.item_name, rec.signal_name,
                        before, None, details))
                elif rec.value is not None:
                    details["prev_status"] = "first_seen" if prev is None else prev[1]
                    events.append(event(
                        EVENT_CONTROL_RESTORED, rec.item_name, rec.signal_name,
                        None, rec.value, details))
            # a signal that vanished from the snapshot (item gone, names changed)
            for key, prev in self._prev.items():
                if key not in controls and prev[0] is not None:
                    events.append(event(
                        EVENT_CONTROL_MISSING, key[1], key[2], prev[0], None, {
                            "cycle_index": cycle_index, "signal_id": prev[3],
                            "prev_cycle_index": prev[2], "status": "absent"}))
            for name, rec in enabled.items():
                prev_en = self._prev_enabled.get(name)
                if prev_en is None or prev_en[0] is None or rec.value is None:
                    continue
                if bool(prev_en[0]) != bool(rec.value):
                    events.append(event(
                        EVENT_ITEM_ENABLED if rec.value else EVENT_ITEM_DISABLED,
                        name, "enabled", prev_en[0], rec.value, {
                            "cycle_index": cycle_index,
                            "prev_cycle_index": prev_en[1]}))

        for key, prev in list(self._prev.items()):
            if key not in controls and prev[0] is not None:
                self._prev[key] = (None, "absent", cycle_index, prev[3])
        for key, (rec, sid) in controls.items():
            self._prev[key] = (rec.value, rec.status, cycle_index, sid)
        for name, rec in enabled.items():
            self._prev_enabled[name] = (rec.value, cycle_index)
        return events


def create_logger_from_env(app: Any) -> "SqliteMeasurementLogger | None":
    """Create a logger from the disable override, DB override, or JSON config."""

    if os.environ.get("DUO_LOG_DISABLE", "").strip().lower() in TRUE_VALUES:
        return None

    try:
        db_override = os.environ.get("DUO_LOG_DB", "").strip()
        if db_override:
            settings = {
                "db_path": db_override,
                "queue_size": _env_int("DUO_LOG_QUEUE_SIZE", 5000, minimum=1),
                "commit_every": _env_int("DUO_LOG_COMMIT_EVERY", 1, minimum=1),
                "print_every": _env_int("DUO_LOG_PRINT_EVERY", 300, minimum=1),
                "min_free_mb": 0,
            }
        else:
            config = _read_config(CONFIG_PATH)
            if config is None or not config["enabled"]:
                return None
            settings = _settings_from_config(
                config, str(getattr(app, "S1_or_S2", "unknown")))
            settings["config_hash"] = _file_sha256(CONFIG_PATH)
        db_path = str(settings["db_path"])
        if not _prepare_storage(db_path, float(settings["min_free_mb"])):
            return None
        return SqliteMeasurementLogger(
            app=app,
            db_path=db_path,
            queue_size=int(settings["queue_size"]),
            commit_every=int(settings["commit_every"]),
            print_every=int(settings["print_every"]),
            min_free_mb=float(settings["min_free_mb"]),
            config_hash=settings.get("config_hash"),
            monthly_dir=settings.get("monthly_dir"),
            month_key=settings.get("month_key"),
        )
    except Exception as ex:
        print("SQLite logger disabled after initialization error:", ex)
        return None


def _env_int(name: str, default: int, minimum: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    value = int(raw)
    return max(minimum, value)


def _read_config(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("top level must be a JSON object")
        return {
            "enabled": raw.get("enabled") is True,
            "base_dir": str(raw["base_dir"]),
            "monthly_files": raw.get("monthly_files", True) is True,
            "commit_every": max(1, int(raw.get("commit_every", 1))),
            "queue_size": max(1, int(raw.get("queue_size", 5000))),
            "print_every": max(1, int(raw.get("print_every", 300))),
            "min_free_mb": max(0.0, float(raw.get("min_free_mb", 5000))),
        }
    except Exception as ex:
        print("SQLite logger config invalid:", path, ex)
        return None


def _settings_from_config(config: dict[str, Any], source: str) -> dict[str, Any]:
    base_dir = Path(config["base_dir"]).expanduser()
    if config["monthly_files"]:
        month = _datetime.datetime.now().strftime("%Y_%m")
        db_path = base_dir / (source + "_" + month + ".db")
    else:
        month = None
        db_path = base_dir / (source + ".db")
    settings = dict(config)
    settings["db_path"] = str(db_path)
    if month is not None:
        settings["monthly_dir"] = str(base_dir)
        settings["month_key"] = month
    return settings


def _file_sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except Exception as ex:
        print("SQLite logger config hash failed:", ex)
        return None


def _next_month_start_unix(month_key: str) -> float:
    """Unix time of local midnight on the 1st of the month after "YYYY_MM".
    Local time, like the monthly file names."""
    year, month = (int(p) for p in month_key.split("_"))
    year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return _datetime.datetime(year, month, 1).timestamp()


def _prepare_storage(db_path: str, min_free_mb: float) -> bool:
    parent = Path(db_path).expanduser().parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        free_mb = _free_mb(parent)
    except Exception as ex:
        print("SQLite logger storage unavailable:", parent, ex)
        return False
    if free_mb < min_free_mb:
        print(
            "SQLite logger disabled: low disk space:",
            round(free_mb, 1), "MB free;", min_free_mb, "MB required",
        )
        return False
    return True


def _free_mb(path: Path) -> float:
    return shutil.disk_usage(path).free / (1024.0 * 1024.0)


class SqliteMeasurementLogger:
    def __init__(
        self,
        app: Any,
        db_path: str,
        queue_size: int = 1000,
        commit_every: int = 1,
        print_every: int = 60,
        min_free_mb: float = 0,
        config_hash: str | None = None,
        monthly_dir: str | None = None,
        month_key: str | None = None,
    ) -> None:
        self.db_path = str(Path(db_path).expanduser())
        self.source = str(getattr(app, "S1_or_S2", "unknown"))
        self.commit_every = commit_every
        self.print_every = print_every
        self.min_free_mb = min_free_mb
        self._queue: queue.Queue[tuple[str, Any]
                                 ] = queue.Queue(maxsize=queue_size)
        self._closed = False
        self._accepting = True
        self._close_lock = threading.Lock()
        self._dropped = 0
        self._logged_cycles = 0
        self._writer_error_reported = False
        self._dropped_events = 0
        # writer-thread-only state for observed parameter-change events
        self._event_tracker = ControlChangeTracker(self.source)
        self._event_errors = 0
        # schema v3 additions (run uuid, meta, loop_dt, rotation); all
        # writer-thread-only except run_uuid/config_hash
        self.run_uuid = uuid.uuid4().hex
        self.config_hash = config_hash
        self._warn_counts: dict[str, int] = {}
        self._prev_monotonic: float | None = None
        self._monthly_dir = monthly_dir
        self._rotate_at: float | None = None
        if monthly_dir and month_key:
            self._rotate_at = _next_month_start_unix(month_key)

        db_parent = Path(self.db_path).parent
        if str(db_parent):
            db_parent.mkdir(parents=True, exist_ok=True)

        self.run_id: int | None = None
        self._init_error: Exception | None = None
        self._ready = threading.Event()
        self._app_title = None
        self._thread = threading.Thread(
            target=self._writer_main, name="duo-sqlite-logger")
        self._thread.daemon = True
        self._thread.start()
        if not self._ready.wait(timeout=10.0):
            self._accepting = False
            raise RuntimeError("SQLite writer initialization timed out")
        if self._init_error is not None:
            raise RuntimeError(
                "SQLite writer initialization failed") from self._init_error
        try:
            atexit.register(self._atexit_close)
        except Exception as ex:
            self._warn("atexit", ex)

        print(
            "SQLite logger enabled:",
            self.db_path,
            "source=" + self.source,
            "run_id=" + str(self.run_id),
        )

    def log_cycle(self, app: Any, cycle_index: int) -> None:
        if self._closed or not self._accepting:
            return
        try:
            snapshot = self._snapshot_cycle(app, cycle_index)
            self._queue.put_nowait(("cycle", snapshot))
        except queue.Full:
            self._dropped += 1
            if self._dropped == 1 or self._dropped % self.print_every == 0:
                print("SQLite logger queue full; dropped cycles:", self._dropped)
        except Exception as ex:
            print("SQLite logger snapshot failed:", ex)

    def log_event(
        self,
        event_type: str,
        item_name: str | None = None,
        signal_name: str | None = None,
        value_before: Any = None,
        value_after: Any = None,
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Queue one event; returns False if it was not accepted. Never raises
        or blocks, so it is safe to call from the Tk main thread."""
        if self._closed or not self._accepting:
            return False
        try:
            ts_unix = time.time()
            event = {
                "ts_utc": _utc_from_unix(ts_unix),
                "ts_unix": ts_unix,
                "ts_mono": time.monotonic(),
                "event_type": str(event_type),
                "item_name": None if item_name is None else str(item_name),
                "signal_name": None if signal_name is None else str(signal_name),
                "value_before": None if value_before is None else str(value_before),
                "value_after": None if value_after is None else str(value_after),
                "details_json": json.dumps(details or {}, sort_keys=True, default=str),
            }
            self._queue.put_nowait(("event", event))
            return True
        except queue.Full:
            self._dropped += 1
            self._dropped_events += 1
            if self._dropped_events == 1 or self._dropped_events % self.print_every == 0:
                print("SQLite logger queue full; dropped events:",
                      self._dropped_events, "last:", event_type)
            return False
        except Exception as ex:
            print("SQLite logger event failed:", event_type, ex)
            return False

    def log_note(self, text: str, cycle_index: int | None = None) -> bool:
        """Queue an operator note; returns False if it was not accepted.

        Never blocks: the row is inserted later by the writer thread. If that
        insert fails, the writer appends the note to the fallback text file.
        """
        if self._closed or not self._accepting:
            return False
        try:
            ts_unix = time.time()
            note = {
                "ts_utc": _utc_from_unix(ts_unix),
                "ts_unix": ts_unix,
                "cycle_index": None if cycle_index is None else int(cycle_index),
                "source": self.source,
                "text": str(text),
            }
            self._queue.put_nowait(("note", note))
            return True
        except queue.Full:
            self._dropped += 1
            print("SQLite logger queue full; dropped note")
            return False
        except Exception as ex:
            print("SQLite logger note failed:", ex)
            return False

    def _atexit_close(self) -> None:
        # clean interpreter exit without on_destroy still records stop_utc
        try:
            self.close()
        except Exception:
            pass

    def _warn(self, what: str, *msg: Any) -> None:
        """Rate-limited warning for failures in the schema v3 additions."""
        n = self._warn_counts.get(what, 0) + 1
        self._warn_counts[what] = n
        if n == 1 or n % self.print_every == 0:
            print("SQLite logger " + what + " failed:", *msg, "count=" + str(n))

    def close(self) -> None:
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            try:
                atexit.unregister(self._atexit_close)
            except Exception:
                pass
            try:
                self._queue.put(("close", None), timeout=2.0)
            except queue.Full:
                print("SQLite logger close timed out while queue was full.")
                return
        self._thread.join(timeout=10.0)
        if self._thread.is_alive():
            print("SQLite logger writer thread did not stop within timeout.")
        else:
            print(
                "SQLite logger closed:",
                "cycles=" + str(self._logged_cycles),
                "dropped=" + str(self._dropped),
            )

    def _initialize_database(self, conn: sqlite3.Connection,
                             continued: bool = False) -> int:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.executescript(SCHEMA_SQL)
        conn.execute("PRAGMA user_version = " + str(SCHEMA_VERSION))
        started_unix = time.time()
        cur = conn.execute(
            """
            INSERT INTO run (
                source, started_utc, started_unix, hostname, pid,
                app_title, db_path, db_schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.source,
                _utc_from_unix(started_unix),
                started_unix,
                _safe_hostname(),
                os.getpid(),
                self._app_title,
                self.db_path,
                SCHEMA_VERSION,
            ),
        )
        conn.commit()
        run_id = int(cur.lastrowid)
        self._apply_additive_schema(conn, run_id, continued)
        return run_id

    def _apply_additive_schema(self, conn: sqlite3.Connection, run_id: int,
                               continued: bool) -> None:
        # Each step is guarded separately; none of them may stop cycle logging.
        for table, column, decl in ADDITIVE_COLUMNS:
            try:
                cols = [r[1] for r in conn.execute(
                    "PRAGMA table_info(" + table + ")")]
                if column not in cols:
                    conn.execute("ALTER TABLE " + table + " ADD COLUMN "
                                 + column + " " + decl)
                    conn.commit()
            except Exception as ex:
                self._warn("schema", table + "." + column, ex)
        try:
            conn.executescript(ADDITIVE_SCHEMA_SQL)
        except Exception as ex:
            self._warn("schema", ex)
        try:
            measurement_cols = [r[1] for r in conn.execute(
                "PRAGMA table_info(measurement)")]
            conn.executemany(
                "INSERT OR IGNORE INTO meta (key, value) VALUES (?, ?)",
                [("schema_version", str(SCHEMA_VERSION)),
                 ("created_utc", _utc_from_unix(time.time())),
                 ("measurement_fields_json", json.dumps(measurement_cols))])
            conn.commit()
        except Exception as ex:
            self._warn("meta", ex)
        try:
            conn.execute(
                "UPDATE run SET run_uuid = ?, config_hash = ?,"
                " continued_from_rotation = ? WHERE id = ?",
                (self.run_uuid, self.config_hash, 1 if continued else 0, run_id))
            conn.commit()
        except Exception as ex:
            self._warn("run", ex)

    def _mark_stopped(self, conn: sqlite3.Connection) -> None:
        # Only on a clean close or rotation; a NULL stop_utc means crash/kill.
        try:
            conn.execute("UPDATE run SET stop_utc = ? WHERE id = ?",
                         (_utc_from_unix(time.time()), self.run_id))
            conn.commit()
        except Exception as ex:
            self._warn("run stop", ex)

    def _write_timing(self, conn: sqlite3.Connection, cycle_id: int,
                      snapshot: dict[str, Any]) -> None:
        try:
            mono = snapshot["monotonic_s"]
            prev, self._prev_monotonic = self._prev_monotonic, mono
            conn.execute(
                "INSERT INTO cycle_timing (cycle_id, loop_dt) VALUES (?, ?)",
                (cycle_id, None if prev is None else mono - prev))
        except Exception as ex:
            self._warn("loop_dt", ex)

    def _maybe_rotate(
        self,
        conn: sqlite3.Connection,
        signal_ids: dict[tuple[Any, ...], int],
        snapshot: dict[str, Any],
    ) -> sqlite3.Connection:
        """Switch to the next monthly file when the cycle's (read-time)
        timestamp crosses local month start. On any failure keep logging to
        the current file and retry a minute later."""
        if self._rotate_at is None or snapshot["ts_unix"] < self._rotate_at:
            return conn
        new_conn = None
        try:
            month = _datetime.datetime.fromtimestamp(
                snapshot["ts_unix"]).strftime("%Y_%m")
            new_path = str(Path(self._monthly_dir or ".").expanduser()
                           / (self.source + "_" + month + ".db"))
            new_conn = sqlite3.connect(new_path, timeout=30.0)
            new_run_id = self._initialize_database(new_conn, continued=True)
        except Exception as ex:
            self._warn("rotation", ex)
            if new_conn is not None:
                try:
                    new_conn.close()
                except Exception:
                    pass
            self._rotate_at = snapshot["ts_unix"] + 60.0
            return conn
        self._mark_stopped(conn)
        try:
            conn.commit()
            conn.close()
        except Exception as ex:
            self._warn("rotation close", ex)
        print("SQLite logger rotated:", self.db_path, "->", new_path)
        self.db_path = new_path
        self.run_id = new_run_id
        self._rotate_at = _next_month_start_unix(month)
        signal_ids.clear()  # signal ids are per file
        # fresh tracker: the first cycle in the new file is a baseline only
        self._event_tracker = ControlChangeTracker(self.source)
        return new_conn

    def _writer_main(self) -> None:
        conn: sqlite3.Connection | None = None
        signal_ids: dict[tuple[Any, ...], int] = {}
        pending = 0
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            self.run_id = self._initialize_database(conn)
            self._ready.set()
            while True:
                kind, payload = self._queue.get()
                try:
                    if kind == "close":
                        conn.commit()
                        self._mark_stopped(conn)
                        return
                    if kind == "cycle":
                        conn = self._maybe_rotate(conn, signal_ids, payload)
                        cycle_id = self._write_cycle(conn, signal_ids, payload)
                        self._write_timing(conn, cycle_id, payload)
                        self._write_observed_events(conn, signal_ids, payload)
                        pending += 1
                        self._logged_cycles += 1
                        if self._logged_cycles % self.print_every == 0:
                            print(
                                "SQLite logger status:",
                                "cycles=" + str(self._logged_cycles),
                                "queue=" + str(self._queue.qsize()),
                                "dropped=" + str(self._dropped),
                            )
                            if self.min_free_mb and _free_mb(Path(self.db_path).parent) < self.min_free_mb:
                                self._accepting = False
                                print(
                                    "SQLite logger stopped accepting cycles: low disk space")
                    elif kind == "event":
                        # A failed event must not stop cycle logging.
                        try:
                            self._write_event(conn, payload)
                            pending += 1
                        except Exception as ex:
                            self._warn("event insert", ex)
                    elif kind == "note":
                        # A failed note must not stop cycle logging; the
                        # note goes to the fallback text file instead.
                        try:
                            self._write_note(conn, payload)
                            conn.commit()
                        except Exception as ex:
                            print("SQLite note insert failed:", ex)
                            self._note_to_fallback_file(payload)
                    if pending >= self.commit_every:
                        conn.commit()
                        pending = 0
                except Exception as ex:
                    self._accepting = False
                    if not self._writer_error_reported:
                        self._writer_error_reported = True
                        print("SQLite logger disabled after writer error:", ex)
                finally:
                    self._queue.task_done()
        except Exception as ex:
            self._init_error = ex
            self._accepting = False
            self._ready.set()
            print("SQLite logger writer stopped:", ex)
        finally:
            if conn is not None:
                try:
                    conn.commit()
                except sqlite3.Error:
                    pass
                conn.close()

    def _write_cycle(
        self,
        conn: sqlite3.Connection,
        signal_ids: dict[tuple[Any, ...], int],
        snapshot: dict[str, Any],
    ) -> None:
        cur = conn.execute(
            """
            INSERT INTO cycle (
                run_id, cycle_index, ts_utc, ts_unix, monotonic_s
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                self.run_id,
                snapshot["cycle_index"],
                snapshot["ts_utc"],
                snapshot["ts_unix"],
                snapshot["monotonic_s"],
            ),
        )
        cycle_id = int(cur.lastrowid)
        for rec in snapshot["measurements"]:
            signal_id = self._signal_id(conn, signal_ids, rec)
            conn.execute(
                """
                INSERT INTO measurement (
                    cycle_id, signal_id, value, band_min, band_max,
                    value_text, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cycle_id,
                    signal_id,
                    rec.value,
                    rec.band_min,
                    rec.band_max,
                    rec.value_text,
                    rec.status,
                ),
            )
        return cycle_id

    def _write_event(self, conn: sqlite3.Connection, event: dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO event (
                run_id, ts_utc, ts_unix, event_type, item_name,
                signal_name, value_before, value_after, details_json, ts_mono
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.run_id,
                event["ts_utc"],
                event["ts_unix"],
                event["event_type"],
                event["item_name"],
                event["signal_name"],
                event["value_before"],
                event["value_after"],
                event["details_json"],
                event.get("ts_mono"),
            ),
        )

    def _write_observed_events(
        self,
        conn: sqlite3.Connection,
        signal_ids: dict[tuple[Any, ...], int],
        snapshot: dict[str, Any],
    ) -> None:
        # A failure here must never stop cycle logging.
        try:
            events = self._event_tracker.process(
                snapshot, lambda rec: self._signal_id(conn, signal_ids, rec))
            for event in events:
                self._write_event(conn, event)
        except Exception as ex:
            self._event_errors += 1
            if self._event_errors == 1 or self._event_errors % self.print_every == 0:
                print("SQLite logger observed-event diff failed:",
                      ex, "count=" + str(self._event_errors))

    def _write_note(self, conn: sqlite3.Connection, note: dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO note (
                run_id, ts_utc, ts_unix, cycle_index, source, text
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                self.run_id,
                note["ts_utc"],
                note["ts_unix"],
                note["cycle_index"],
                note["source"],
                note["text"],
            ),
        )

    def _note_to_fallback_file(self, note: dict[str, Any]) -> None:
        try:
            path = append_note_fallback(
                Path(self.db_path).parent, note["source"], note["text"],
                note["ts_unix"])
            print("Note saved to fallback file:", path)
        except Exception as ex:
            print("Note fallback file failed:", ex, "note text:", note.get("text"))

    def _signal_id(
        self,
        conn: sqlite3.Connection,
        signal_ids: dict[tuple[Any, ...], int],
        rec: MeasurementRecord,
    ) -> int:
        channel_index = -1 if rec.channel_index is None else rec.channel_index
        key = (
            self.source,
            rec.item_name,
            rec.signal_name,
            rec.signal_kind,
            channel_index,
        )
        if key in signal_ids:
            return signal_ids[key]
        conn.execute(
            """
            INSERT OR IGNORE INTO signal (
                source, item_name, signal_name, signal_kind,
                channel_index, unit, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            key + (rec.unit, rec.metadata_json),
        )
        row = conn.execute(
            """
            SELECT id FROM signal
            WHERE source = ?
              AND item_name = ?
              AND signal_name = ?
              AND signal_kind = ?
              AND channel_index IS ?
            """,
            key,
        ).fetchone()
        if row is None:
            raise RuntimeError("failed to create signal row: " + repr(key))
        signal_ids[key] = int(row[0])
        return signal_ids[key]

    def _snapshot_cycle(self, app: Any, cycle_index: int) -> dict[str, Any]:
        ts_unix = time.time()
        measurements: list[MeasurementRecord] = []
        items = list(getattr(app, "the_items", []) or [])

        for item_index, item in enumerate(items):
            fallback_item_name = str(
                getattr(item, "the_name", "item_" + str(item_index))
            )

            for attr_name in ("enabled", "is_master", "time_to_get_ms"):
                if hasattr(item, attr_name):
                    measurements.append(
                        self._attr_record(
                            fallback_item_name,
                            attr_name,
                            "item_attr",
                            getattr(item, attr_name),
                        )
                    )

            measurements.extend(
                self._structured_item_records(item, fallback_item_name)
            )

        if hasattr(app, "bpm"):
            value, band_min, band_max, value_text, status = _coerce_value(
                getattr(app, "bpm")
            )
            measurements.append(
                MeasurementRecord(
                    item_name="app",
                    signal_name="bpm",
                    signal_kind="app_attr",
                    channel_index=None,
                    unit=None,
                    metadata_json=None,
                    value=value,
                    band_min=band_min,
                    band_max=band_max,
                    value_text=value_text,
                    status=status,
                )
            )

        return {
            "cycle_index": int(cycle_index),
            "ts_utc": _utc_from_unix(ts_unix),
            "ts_unix": ts_unix,
            "monotonic_s": time.monotonic(),
            "measurements": measurements,
        }

    def _structured_item_records(
        self,
        item: Any,
        fallback_item_name: str,
    ) -> list[MeasurementRecord]:
        records: list[MeasurementRecord] = []
        status: str | None = None
        item_name = fallback_item_name

        names = getattr(item, "last_names", None)
        ctrl = _as_list(getattr(item, "last_ctrl", None))
        ret = _as_list(getattr(item, "last_ret", None))

        if names is None:
            status = "missing_names"
            control_names = ["channel_" + str(i) for i in range(len(ctrl))]
            readout_names = ["channel_" + str(i) for i in range(len(ret))]
        else:
            try:
                names_list = [str(name) for name in list(names)]
            except TypeError:
                names_list = []
            expected_len = 1 + len(ctrl) + len(ret)
            if len(names_list) == expected_len:
                item_name = names_list[0]
                control_names = names_list[1:1 + len(ctrl)]
                readout_names = names_list[1 + len(ctrl):]
            else:
                status = "name_mismatch"
                control_names = ["channel_" + str(i) for i in range(len(ctrl))]
                readout_names = ["channel_" + str(i) for i in range(len(ret))]

        item_enabled = _safe_bool(getattr(item, "enabled", None))
        for channel_index, raw_value in enumerate(ctrl):
            value, band_min, band_max, value_text, value_status = _coerce_value(
                raw_value
            )
            records.append(
                MeasurementRecord(
                    item_name=item_name,
                    signal_name=control_names[channel_index],
                    signal_kind="control",
                    channel_index=channel_index,
                    unit=None,
                    metadata_json=None,
                    value=value,
                    band_min=band_min,
                    band_max=band_max,
                    value_text=value_text,
                    status=_join_status(status, value_status),
                )
            )

        for channel_index, raw_value in enumerate(ret):
            value, band_min, band_max, value_text, value_status = _coerce_value(
                raw_value
            )
            readout_status = _join_status(status, value_status)
            if item_enabled is False:
                readout_status = _join_status(
                    "disabled_cached", readout_status)
            records.append(
                MeasurementRecord(
                    item_name=item_name,
                    signal_name=readout_names[channel_index],
                    signal_kind="readout",
                    channel_index=channel_index,
                    unit=None,
                    metadata_json=None,
                    value=value,
                    band_min=band_min,
                    band_max=band_max,
                    value_text=value_text,
                    status=readout_status,
                )
            )

        return records

    def _attr_record(
        self,
        item_name: str,
        attr_name: str,
        signal_kind: str,
        raw_value: Any,
    ) -> MeasurementRecord:
        value, band_min, band_max, value_text, status = _coerce_value(
            raw_value)
        return MeasurementRecord(
            item_name=item_name,
            signal_name=attr_name,
            signal_kind=signal_kind,
            channel_index=None,
            unit=None,
            metadata_json=None,
            value=value,
            band_min=band_min,
            band_max=band_max,
            value_text=value_text,
            status=status,
        )


def _coerce_value(raw: Any) -> tuple[float | None, float | None, float | None, str | None, str | None]:
    if isinstance(raw, tuple):
        value_raw = raw[0] if len(raw) > 0 else None
        band_min_raw = raw[1] if len(raw) > 1 else None
        band_max_raw = raw[2] if len(raw) > 2 else None
        value, value_text, status = _float_or_text(value_raw)
        band_min, band_min_text, band_min_status = _float_or_text(band_min_raw)
        band_max, band_max_text, band_max_status = _float_or_text(band_max_raw)
        texts = [t for t in (value_text, band_min_text,
                             band_max_text) if t is not None]
        statuses = [s for s in (status, band_min_status, band_max_status) if s]
        return (
            value,
            band_min,
            band_max,
            "; ".join(texts) if texts else None,
            ",".join(statuses) if statuses else None,
        )
    value, value_text, status = _float_or_text(raw)
    return value, None, None, value_text, status


def _float_or_text(raw: Any) -> tuple[float | None, str | None, str | None]:
    if raw is None:
        return None, None, "missing"
    try:
        value = float(raw)
    except Exception:
        return None, str(raw), "non_numeric"
    if math.isnan(value) or math.isinf(value):
        return None, str(raw), "non_finite"
    return value, None, None


def _join_status(primary: str | None, secondary: str | None) -> str | None:
    if not primary:
        return secondary
    if not secondary:
        return primary
    if secondary == primary:
        return primary
    return primary + "," + secondary


def _as_list(raw: Any) -> list[Any]:
    if raw is None:
        return []
    try:
        return list(raw)
    except TypeError:
        return [raw]


def _safe_bool(raw: Any) -> bool | None:
    if raw is None:
        return None
    try:
        return bool(raw)
    except Exception:
        return None


def _safe_hostname() -> str | None:
    try:
        return os.uname().nodename
    except Exception:
        return None


def note_fallback_path(directory: Any, source: str, ts_unix: float | None = None) -> Path:
    """Path of the monthly text file used when a note cannot go to SQLite."""
    if ts_unix is None:
        ts_unix = time.time()
    month = _datetime.datetime.fromtimestamp(ts_unix).strftime("%Y_%m")
    return Path(directory).expanduser() / ("notes_" + str(source) + "_" + month + ".txt")


def append_note_fallback(directory: Any, source: str, text: str, ts_unix: float | None = None) -> Path:
    """Append one tab-separated line (ts_utc, source, text) to the fallback file."""
    if ts_unix is None:
        ts_unix = time.time()
    path = note_fallback_path(directory, source, ts_unix)
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = " ".join(str(text).split())
    with open(str(path), "a", encoding="utf-8") as f:
        f.write(_utc_from_unix(ts_unix) + "\t" + str(source) + "\t" + clean + "\n")
    return path


def _utc_from_unix(ts_unix: float) -> str:
    return (
        _datetime.datetime.fromtimestamp(ts_unix, tz=_datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


class _MockMaster:
    def __init__(self, text: str) -> None:
        self._text = text

    def cget(self, key: str) -> str:
        if key == "text":
            return self._text
        return ""


class _MockCheckbutton:
    def __init__(self, master_text: str, text: str) -> None:
        self.master = _MockMaster(master_text)
        self._text = text

    def cget(self, key: str) -> str:
        if key == "text":
            return self._text
        return ""


class _MockItem:
    def __init__(self, name: str, labels: list[str], current: float, f_value: float) -> None:
        self.the_name = name
        self._readout_labels = labels
        self.enabled = True
        self.is_master = True
        self.slave = None
        self.current = current
        self.F = f_value
        self.CR = 0.0
        self.VR = 0.0
        self.FR = 0.0
        self.time_to_get_ms = 1
        self.last_names: list[str] = []
        self.last_ctrl: list[Any] = []
        self.last_ret: list[Any] = []
        self.the_checkbuttons = [_MockCheckbutton(
            name, label) for label in labels]
        self.refresh_last_values()

    def refresh_last_values(self) -> None:
        self.last_ctrl = [self.current, self.F]
        self.last_names = [self.the_name,
                           "current", "F"] + self._readout_labels


class _MockApp:
    def __init__(self, source: str) -> None:
        self.S1_or_S2 = source
        self.the_items = [
            _MockItem("Pressure", ["Pressure p"], 0.0, 0.0),
            _MockItem("Arc", ["Arc I", "Arc U"], 42.0, 18.0),
            _MockItem("Extraction", ["Extraction I",
                      "Extraction U"], 10.0, 0.0),
            _MockItem("Beam", ["Beam current"], 0.0, 0.0),
        ]
        self.bpm = 0.0


def _run_mock(seconds: int, db_path: str, source: str, seed: int) -> None:
    rng = random.Random(seed)
    app = _MockApp(source)
    logger = SqliteMeasurementLogger(
        app, db_path, queue_size=1000, commit_every=1)
    start = time.monotonic()
    cycles = 0
    try:
        while time.monotonic() - start < seconds:
            cycles += 1
            t = cycles
            pressure = 3.0 + 0.08 * math.sin(t / 20.0) + rng.gauss(0, 0.015)
            arc = app.the_items[1]
            extraction = app.the_items[2]
            beam = app.the_items[3]

            # setpoints are steady except for: an operator knob change on
            # Extraction at cycle 2 (with its setpoint_request, as the GUI's
            # on_change_ctrl_proc would log it), a worker-thread-style ramp
            # of the Arc setpoint over cycles 3-5 (no request), and Beam
            # disabled at cycle 4 / re-enabled at cycle 6.
            arc.current = 42.0 + 0.5 * min(max(t - 2, 0), 3)
            arc.F = 18.0
            arc.CR = 1.55 + rng.gauss(0, 0.015)
            arc.VR = 78.0 + rng.gauss(0, 0.8)
            extraction.current = 10.5 if t >= 2 else 10.0
            if t == 2:
                logger.log_event(EVENT_SETPOINT_REQUEST, item_name="Extraction",
                                 signal_name="current", value_after=10.5,
                                 details={"mock": True})
            if t == 4:
                beam.enabled = False
            if t == 6:
                beam.enabled = True
            extraction.CR = 0.32 + rng.gauss(0, 0.01)
            extraction.VR = extraction.current + rng.gauss(0, 0.02)
            app.bpm = (
                120.0
                + 2.0 * (arc.current - 42.0)
                + 1.5 * (extraction.current - 10.0)
                - 8.0 * abs(pressure - 3.0)
                + rng.gauss(0, 1.2)
            )
            beam.CR = app.bpm

            if rng.random() < 0.05:
                app.the_items[0].last_ret = [None]
            else:
                app.the_items[0].last_ret = [pressure]
            arc.last_ret = [
                (arc.CR, arc.CR - 0.04, arc.CR + 0.04),
                (arc.VR, arc.VR - 1.5, arc.VR + 1.5),
            ]
            extraction.last_ret = [
                (extraction.CR, extraction.CR - 0.02, extraction.CR + 0.02),
                (extraction.VR, extraction.VR - 0.05, extraction.VR + 0.05),
            ]
            beam.last_ret = [app.bpm]
            for item in app.the_items:
                item.refresh_last_values()
            if cycles % 10 == 0:
                app.the_items[0].last_names = None
            if cycles % 15 == 0:
                arc.last_names = ["Arc", "too_few_names"]

            logger.log_cycle(app, cycles)
            if cycles == 3:
                logger.log_note("mock note: good performance here", cycles)
            if cycles == 6:
                logger.log_note("mock note: bad data, don't use", cycles)
            time.sleep(1.0)
        logger.log_note("mock note: end of mock run", cycles)
    finally:
        logger.close()

    _print_mock_summary(db_path, cycles)


def _print_mock_summary(db_path: str, cycles: int) -> None:
    conn = sqlite3.connect(db_path)
    try:
        measurement_count = conn.execute(
            "SELECT COUNT(*) FROM measurement").fetchone()[0]
        signal_count = conn.execute(
            "SELECT COUNT(*) FROM signal").fetchone()[0]
        row = conn.execute(
            "SELECT MIN(ts_utc), MAX(ts_utc) FROM cycle").fetchone()
        print("Mock DB path:", db_path)
        print("Mock cycles requested:", cycles)
        print("DB cycles:", conn.execute(
            "SELECT COUNT(*) FROM cycle").fetchone()[0])
        print("DB measurements:", measurement_count)
        print("DB signals:", signal_count)
        print("DB notes:", _count_table(conn, "note"))
        print("DB events:", _count_table(conn, "event"))
        print("First timestamp:", row[0])
        print("Last timestamp:", row[1])
    finally:
        conn.close()


def _inspect_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=5000")
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        print("DB path:", db_path)
        print("Tables:", ", ".join(tables) if tables else "[none]")
        print("Run count:", _count_table(conn, "run"))
        print("Cycle count:", _count_table(conn, "cycle"))
        print("Signal count:", _count_table(conn, "signal"))
        print("Measurement count:", _count_table(conn, "measurement"))
        print("Event count:", _count_table(conn, "event"))
        print("Note count:", _count_table(conn, "note"))
        print("Meta count:", _count_table(conn, "meta"))
        print("Cycle timing count:", _count_table(conn, "cycle_timing"))
        print("Schema version (user_version):",
              conn.execute("PRAGMA user_version").fetchone()[0])
        _print_last_rows(conn, "run", 5)
        _print_last_rows(conn, "meta", 20, order="key")
        try:
            row = conn.execute(
                "SELECT COUNT(loop_dt), MIN(loop_dt), AVG(loop_dt), MAX(loop_dt)"
                " FROM cycle_timing").fetchone()
            print("loop_dt s (n, min, avg, max):", row)
        except sqlite3.Error as ex:
            print("loop_dt: [unavailable: " + str(ex) + "]")
        print("Last 10 notes:")
        for row in _fetch_notes(conn, last=10):
            print("  " + _format_note(row))
        print("Events by type:")
        try:
            for event_type, count in conn.execute(
                "SELECT event_type, COUNT(*) FROM event GROUP BY event_type"
                " ORDER BY COUNT(*) DESC, event_type"
            ):
                print(f"  {event_type}\t{count}")
        except sqlite3.Error as ex:
            print("  [unavailable: " + str(ex) + "]")
        print("Last 10 events:")
        for row in _fetch_events(conn, last=10):
            print("  " + _format_event(row))
        print("Signal kinds:")
        for kind, count in conn.execute(
            "SELECT signal_kind, COUNT(*) FROM signal GROUP BY signal_kind ORDER BY signal_kind"
        ):
            print(f"  {kind}\t{count}")
        row = conn.execute(
            "SELECT MIN(ts_utc), MAX(ts_utc) FROM cycle").fetchone()
        print("Min timestamp:", row[0])
        print("Max timestamp:", row[1])
        print(
            "app_attr bpm exists:",
            bool(conn.execute(
                "SELECT 1 FROM signal WHERE signal_kind='app_attr' AND signal_name='bpm' LIMIT 1"
            ).fetchone()),
        )
        print("Rows with non-null status:")
        for status, count in conn.execute(
            """
            SELECT status, COUNT(*) FROM measurement
            WHERE status IS NOT NULL
            GROUP BY status ORDER BY COUNT(*) DESC, status
            """
        ):
            print(f"  {status}\t{count}")
        print("Top 30 signals:")
        for item_name, signal_name, signal_kind, count in conn.execute(
            """
            SELECT s.item_name, s.signal_name, s.signal_kind, COUNT(*)
            FROM measurement m
            JOIN signal s ON s.id = m.signal_id
            GROUP BY s.id
            ORDER BY COUNT(*) DESC, s.item_name, s.signal_name
            LIMIT 30
            """
        ):
            print(f"  {item_name}\t{signal_name}\t{signal_kind}\t{count}")
    finally:
        conn.close()


def _fetch_notes(conn: sqlite3.Connection, last: int | None = None) -> list[tuple[Any, ...]]:
    sql = "SELECT ts_utc, source, cycle_index, run_id, text FROM note"
    try:
        if last is None:
            return conn.execute(sql + " ORDER BY ts_unix, id").fetchall()
        rows = conn.execute(
            sql + " ORDER BY ts_unix DESC, id DESC LIMIT ?", (int(last),)).fetchall()
        return list(reversed(rows))
    except sqlite3.Error:
        return []


def _format_note(row: tuple[Any, ...]) -> str:
    ts_utc, source, cycle_index, run_id, text = row
    return "\t".join([
        str(ts_utc), str(source), "cycle=" + str(cycle_index),
        "run=" + str(run_id), str(text)])


def _list_notes(db_path: str) -> int:
    if not Path(db_path).exists():
        print("DB not found:", db_path)
        return 1
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=5000")
        rows = _fetch_notes(conn)
        print("DB path:", db_path)
        print("Notes:", len(rows))
        for row in rows:
            print(_format_note(row))
    finally:
        conn.close()
    return 0


def _parse_since(since: str) -> float:
    """ISO date/time -> Unix time. A value without a timezone is taken as UTC,
    like the ts_utc column; a trailing Z is accepted."""
    text = since.strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    dt = _datetime.datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_datetime.timezone.utc)
    return dt.timestamp()


def _fetch_events(
    conn: sqlite3.Connection,
    last: int | None = None,
    item: str | None = None,
    since_unix: float | None = None,
    event_type: str | None = None,
) -> list[tuple[Any, ...]]:
    sql = ("SELECT ts_utc, event_type, item_name, signal_name, value_before,"
           " value_after, run_id, details_json FROM event")
    where: list[str] = []
    args: list[Any] = []
    if item is not None:
        where.append("item_name = ?")
        args.append(item)
    if since_unix is not None:
        where.append("ts_unix >= ?")
        args.append(since_unix)
    if event_type is not None:
        where.append("event_type = ?")
        args.append(event_type)
    if where:
        sql += " WHERE " + " AND ".join(where)
    try:
        if last is None:
            return conn.execute(sql + " ORDER BY ts_unix, id", args).fetchall()
        rows = conn.execute(
            sql + " ORDER BY ts_unix DESC, id DESC LIMIT ?", args + [int(last)]).fetchall()
        return list(reversed(rows))
    except sqlite3.Error:
        return []


def _format_event(row: tuple[Any, ...]) -> str:
    ts_utc, event_type, item_name, signal_name, before, after, run_id, details = row
    return "\t".join([
        str(ts_utc), str(event_type), str(item_name), str(signal_name),
        str(before) + " -> " + str(after), "run=" + str(run_id), str(details)])


def _list_events(
    db_path: str,
    item: str | None = None,
    since: str | None = None,
    event_type: str | None = None,
) -> int:
    if not Path(db_path).exists():
        print("DB not found:", db_path)
        return 1
    since_unix = None
    if since:
        try:
            since_unix = _parse_since(since)
        except ValueError as ex:
            print("Invalid --since (use ISO, e.g. 2026-09-30T08:00):", ex)
            return 2
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=5000")
        rows = _fetch_events(conn, item=item, since_unix=since_unix,
                             event_type=event_type)
        print("DB path:", db_path)
        print("Events:", len(rows))
        for row in rows:
            print(_format_event(row))
    finally:
        conn.close()
    return 0


def _check_config() -> int:
    print("Config path:", CONFIG_PATH)
    config = _read_config(CONFIG_PATH)
    if config is None:
        print("Auto-enable: no")
        return 1
    print("Auto-enable:", "yes" if config["enabled"] else "no")
    if not config["enabled"]:
        return 0
    settings = _settings_from_config(config, "TEST")
    print("Calculated DB path:", settings["db_path"])
    base_dir = Path(config["base_dir"]).expanduser()
    try:
        probe = base_dir if base_dir.exists() else base_dir.parent
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        print("Free disk space in base_dir:", round(_free_mb(probe), 1), "MB",
              "(checked filesystem at " + str(probe) + ")")
    except Exception as ex:
        print("Free disk space unavailable:", ex)
        return 1
    return 0


def _print_last_rows(conn: sqlite3.Connection, table_name: str, last: int,
                     order: str = "rowid DESC") -> None:
    """Print the last rows of a table with whatever columns it has; old DB
    files without the table print [unavailable] (--inspect never creates)."""
    print("Last " + str(last) + " " + table_name + " rows:")
    try:
        cur = conn.execute(
            f"SELECT * FROM {table_name} ORDER BY {order} LIMIT ?", (int(last),))
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        if order.endswith("DESC"):
            rows.reverse()
        print("  " + "\t".join(cols))
        for row in rows:
            print("  " + "\t".join(str(v) for v in row))
    except sqlite3.Error as ex:
        print("  [unavailable: " + str(ex) + "]")


def _count_table(conn: sqlite3.Connection, table_name: str) -> int:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
    except sqlite3.Error:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Duoplasmatron SQLite logger")
    parser.add_argument("--mock", action="store_true",
                        help="run local mock logger test")
    parser.add_argument("--inspect", action="store_true",
                        help="inspect an existing logger database")
    parser.add_argument("--check-config", action="store_true",
                        help="validate unattended logger configuration")
    parser.add_argument("--notes", action="store_true",
                        help="list all operator notes in --db")
    parser.add_argument("--events", action="store_true",
                        help="list events in --db (filters: --item, --since, --type)")
    parser.add_argument("--item", default=None,
                        help="--events: exact item_name")
    parser.add_argument("--since", default=None,
                        help="--events: ISO time, UTC unless an offset is given")
    parser.add_argument("--type", dest="event_type", default=None,
                        help="--events: exact event_type")
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--db", default="mock_measurements.db")
    parser.add_argument("--source", default="MOCK_S2")
    parser.add_argument("--seed", type=int, default=123)
    args = parser.parse_args()
    if args.check_config:
        return _check_config()
    if args.inspect:
        _inspect_db(args.db)
        return 0
    if args.notes:
        return _list_notes(args.db)
    if args.events:
        return _list_events(args.db, args.item, args.since, args.event_type)
    if not args.mock:
        parser.error(
            "use --mock to generate data, --inspect to inspect a database, "
            "--notes to list notes, or --events to list events")
    _run_mock(args.seconds, args.db, args.source, args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
