"""Small SQLite store for the live parts of the app: crews, assignments and the
notes crews submit. Everything here is application state created while using the
app (demo inputs), separate from the competition dataset."""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS crews (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, lat REAL, lon REAL, updated TEXT
);
CREATE TABLE IF NOT EXISTS assignments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  uwi TEXT NOT NULL, crew_id TEXT NOT NULL REFERENCES crews(id),
  manager_note TEXT, assigned_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'assigned',      -- assigned | resolved
  work_done TEXT, crew_note TEXT, actual_cost REAL, hours REAL,
  resolved_at TEXT, resolved_lat REAL, resolved_lon REAL
);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_per_well
  ON assignments(uwi) WHERE status = 'assigned';
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript(SCHEMA)

    # ---- crews ----------------------------------------------------------
    def ensure_crews(self, crews: list[tuple[str, str]]) -> None:
        with self.lock:
            for cid, name in crews:
                self.db.execute("INSERT OR IGNORE INTO crews(id, name) VALUES (?, ?)", (cid, name))
            self.db.commit()

    def crews(self) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM crews ORDER BY id")]

    def set_location(self, crew_id: str, lat: float, lon: float) -> bool:
        with self.lock:
            cur = self.db.execute("UPDATE crews SET lat=?, lon=?, updated=? WHERE id=?",
                                  (lat, lon, _now(), crew_id))
            self.db.commit()
            return cur.rowcount == 1

    # ---- assignments ----------------------------------------------------
    def assign(self, uwi: str, crew_id: str, note: str = "") -> int:
        """Raises ValueError if the well already has an open assignment or the crew is unknown."""
        with self.lock:
            if not self.db.execute("SELECT 1 FROM crews WHERE id=?", (crew_id,)).fetchone():
                raise ValueError("unknown crew")
            try:
                cur = self.db.execute(
                    "INSERT INTO assignments(uwi, crew_id, manager_note, assigned_at) VALUES (?,?,?,?)",
                    (uwi, crew_id, note, _now()))
            except sqlite3.IntegrityError:
                raise ValueError("well already assigned") from None
            self.db.commit()
            return int(cur.lastrowid)

    def assignments(self, status: str | None = None, crew_id: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM assignments WHERE 1=1", []
        if status:
            q += " AND status=?"; args.append(status)
        if crew_id:
            q += " AND crew_id=?"; args.append(crew_id)
        with self.lock:
            return [dict(r) for r in self.db.execute(q + " ORDER BY id DESC", args)]

    def get_assignment(self, aid: int) -> dict | None:
        with self.lock:
            r = self.db.execute("SELECT * FROM assignments WHERE id=?", (aid,)).fetchone()
            return dict(r) if r else None

    def resolve(self, aid: int, work_done: str, crew_note: str, actual_cost: float | None,
                hours: float | None, lat: float | None, lon: float | None) -> bool:
        with self.lock:
            cur = self.db.execute(
                "UPDATE assignments SET status='resolved', work_done=?, crew_note=?, actual_cost=?, hours=?, "
                "resolved_at=?, resolved_lat=?, resolved_lon=? WHERE id=? AND status='assigned'",
                (work_done, crew_note, actual_cost, hours, _now(), lat, lon, aid))
            self.db.commit()
            return cur.rowcount == 1

    def open_uwis(self) -> set[str]:
        with self.lock:
            return {r[0] for r in self.db.execute("SELECT uwi FROM assignments WHERE status='assigned'")}

    def resolved_uwis(self) -> set[str]:
        with self.lock:
            return {r[0] for r in self.db.execute("SELECT uwi FROM assignments WHERE status='resolved'")}
