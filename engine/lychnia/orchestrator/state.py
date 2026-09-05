"""Per-project registry in SQLite (spec §6.2): artifacts, runs, events.

The store can be deleted without losing work: statuses are derived from disk and the
Engine reports outputs without a row as `unregistered` until their task runs again.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS artifacts (
  name TEXT PRIMARY KEY, path TEXT NOT NULL, hash TEXT, fingerprint TEXT, producer TEXT,
  produced_at TEXT, approved_hash TEXT, approved_by TEXT, approved_at TEXT, edited INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
  status TEXT NOT NULL, error TEXT, master_limit REAL, log_path TEXT);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, t TEXT NOT NULL, type TEXT NOT NULL, payload TEXT);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class ArtifactRecord:
    name: str
    path: str
    hash: str | None
    fingerprint: str | None
    producer: str | None
    produced_at: str | None
    approved_hash: str | None
    approved_by: str | None
    approved_at: str | None
    edited: bool


@dataclass(frozen=True)
class RunRecord:
    id: int
    task: str
    started_at: str
    finished_at: str | None
    status: str
    error: str | None
    master_limit: float | None
    log_path: str | None


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(_SCHEMA)
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._db.execute(sql, params)
            return cur.fetchall()

    def _execute(self, sql: str, params: tuple = ()) -> int:
        with self._lock:
            cur = self._db.execute(sql, params)
            self._db.commit()
            return int(cur.lastrowid or 0)

    # ── artifacts ────────────────────────────────────────────────────────
    def record_artifact(self, name: str, path: str, hash: str, fingerprint: str, producer: str) -> None:
        self._execute("""INSERT INTO artifacts(name, path, hash, fingerprint, producer, produced_at, edited)
                         VALUES (?, ?, ?, ?, ?, ?, 0)
                         ON CONFLICT(name) DO UPDATE SET path=excluded.path, hash=excluded.hash,
                           fingerprint=excluded.fingerprint, producer=excluded.producer,
                           produced_at=excluded.produced_at, edited=0""",
                      (name, path, hash, fingerprint, producer, _now()))

    def get_artifact(self, name: str) -> ArtifactRecord | None:
        rows = self._query("SELECT * FROM artifacts WHERE name = ?", (name,))
        return self._artifact(rows[0]) if rows else None

    def list_artifacts(self) -> list[ArtifactRecord]:
        return [self._artifact(r) for r in self._query("SELECT * FROM artifacts ORDER BY name")]

    def approve(self, name: str, hash: str, who: str) -> None:
        self._execute("UPDATE artifacts SET approved_hash=?, approved_by=?, approved_at=? WHERE name=?",
                      (hash, who, _now(), name))

    def revoke_approval(self, name: str) -> None:
        self._execute("UPDATE artifacts SET approved_hash=NULL, approved_by=NULL, approved_at=NULL WHERE name=?", (name,))

    def mark_edited(self, name: str, hash: str) -> None:
        self._execute("UPDATE artifacts SET hash=?, edited=1 WHERE name=?", (hash, name))

    @staticmethod
    def _artifact(row: sqlite3.Row) -> ArtifactRecord:
        return ArtifactRecord(row["name"], row["path"], row["hash"], row["fingerprint"], row["producer"],
                              row["produced_at"], row["approved_hash"], row["approved_by"], row["approved_at"],
                              bool(row["edited"]))

    # ── runs ─────────────────────────────────────────────────────────────
    def start_run(self, task: str, master_limit: float | None = None, log_path: str | None = None) -> int:
        return self._execute("INSERT INTO runs(task, started_at, status, master_limit, log_path) VALUES (?, ?, 'queued', ?, ?)",
                             (task, _now(), master_limit, log_path))

    def set_run_status(self, run_id: int, status: str) -> None:
        self._execute("UPDATE runs SET status=? WHERE id=?", (status, run_id))

    def finish_run(self, run_id: int, status: str, error: str | None = None) -> None:
        self._execute("UPDATE runs SET status=?, error=?, finished_at=? WHERE id=?", (status, error, _now(), run_id))

    def get_run(self, run_id: int) -> RunRecord | None:
        rows = self._query("SELECT * FROM runs WHERE id=?", (run_id,))
        return self._runrec(rows[0]) if rows else None

    def latest_run(self, task: str) -> RunRecord | None:
        rows = self._query("SELECT * FROM runs WHERE task=? ORDER BY id DESC LIMIT 1", (task,))
        return self._runrec(rows[0]) if rows else None

    @staticmethod
    def _runrec(row: sqlite3.Row) -> RunRecord:
        return RunRecord(row["id"], row["task"], row["started_at"], row["finished_at"], row["status"],
                         row["error"], row["master_limit"], row["log_path"])

    # ── events ───────────────────────────────────────────────────────────
    def add_event(self, run_id: int | None, type: str, payload: dict) -> None:
        self._execute("INSERT INTO events(run_id, t, type, payload) VALUES (?, ?, ?, ?)",
                      (run_id, _now(), type, json.dumps(payload, ensure_ascii=False)))

    def events_for(self, run_id: int) -> list[tuple[str, str, dict]]:
        rows = self._query("SELECT type, t, payload FROM events WHERE run_id=? ORDER BY id", (run_id,))
        return [(r["type"], r["t"], json.loads(r["payload"])) for r in rows]
