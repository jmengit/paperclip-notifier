from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable


class State:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        # The health server runs in a separate thread and reads summary() while
        # the poller writes the same database.  SQLite connections otherwise
        # reject cross-thread use even though WAL serializes the SQL safely.
        self.db = sqlite3.connect(directory / "state.sqlite3", timeout=30, isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS source_state (
              source_key TEXT PRIMARY KEY, last_created_at TEXT, last_keys TEXT NOT NULL DEFAULT '[]', updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS outbox (
              event_key TEXT NOT NULL, destination TEXT NOT NULL, payload TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
              next_attempt_at REAL NOT NULL DEFAULT 0, last_error TEXT, created_at REAL NOT NULL,
              delivered_at REAL, PRIMARY KEY(event_key, destination)
            );
            CREATE TABLE IF NOT EXISTS recent_seen (
              event_key TEXT PRIMARY KEY, source_created_at TEXT, expires_at REAL NOT NULL
            );
            """
        )

    def known(self, key: str) -> bool:
        with self.lock:
            row = self.db.execute("SELECT 1 FROM recent_seen WHERE event_key=? AND expires_at>?", (key, time.time())).fetchone()
            return row is not None

    def checkpoint_batch(self, source_key: str, rows: Iterable[tuple[str, str, dict[str, Any], Iterable[str]]]) -> None:
        with self.lock:
            now = time.time()
            self.db.execute("BEGIN IMMEDIATE")
            try:
                state = self.db.execute("SELECT last_created_at,last_keys FROM source_state WHERE source_key=?", (source_key,)).fetchone()
                last_at = state["last_created_at"] if state else None
                last_keys = set(json.loads(state["last_keys"]) if state else [])
                for key, created_at, payload, destinations in rows:
                    if self.known(key):
                        continue
                    for destination in destinations:
                        self.db.execute(
                            "INSERT OR IGNORE INTO outbox(event_key,destination,payload,created_at) VALUES(?,?,?,?)",
                            (key, destination, json.dumps(payload, separators=(",", ":"), ensure_ascii=False), now),
                        )
                    self.db.execute("INSERT OR REPLACE INTO recent_seen(event_key,source_created_at,expires_at) VALUES(?,?,?)", (key, created_at, now + 7 * 86400))
                    if last_at is None or created_at > last_at:
                        last_at, last_keys = created_at, {key}
                    elif created_at == last_at:
                        last_keys.add(key)
                if last_at is not None:
                    self.db.execute(
                        "INSERT INTO source_state(source_key,last_created_at,last_keys,updated_at) VALUES(?,?,?,?) ON CONFLICT(source_key) DO UPDATE SET last_created_at=excluded.last_created_at,last_keys=excluded.last_keys,updated_at=excluded.updated_at",
                        (source_key, last_at, json.dumps(sorted(last_keys)), now),
                    )
                self.db.execute("DELETE FROM recent_seen WHERE expires_at<?", (now,))
                self.db.execute("COMMIT")
            except Exception:
                self.db.execute("ROLLBACK")
                raise

    def pending(self, limit: int = 25) -> list[sqlite3.Row]:
        with self.lock:
            return self.db.execute("SELECT * FROM outbox WHERE status='pending' AND next_attempt_at<=? ORDER BY created_at LIMIT ?", (time.time(), limit)).fetchall()

    def deliver_success(self, event_key: str, destination: str) -> None:
        with self.lock:
            self.db.execute("UPDATE outbox SET status='delivered',delivered_at=? WHERE event_key=? AND destination=?", (time.time(), event_key, destination))

    def deliver_retry(self, event_key: str, destination: str, attempts: int, next_at: float, error: str, dead: bool = False) -> None:
        with self.lock:
            self.db.execute("UPDATE outbox SET status=?,attempts=?,next_attempt_at=?,last_error=? WHERE event_key=? AND destination=?", ("dead" if dead else "pending", attempts, next_at, error[:500], event_key, destination))

    def summary(self) -> dict[str, int]:
        with self.lock:
            return {row["status"]: row["count"] for row in self.db.execute("SELECT status,COUNT(*) count FROM outbox GROUP BY status")}

    def close(self) -> None:
        with self.lock:
            self.db.close()
