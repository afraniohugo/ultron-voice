"""SQLite registry: persists dub/audiobook jobs and their history.

Each successful or failed run is recorded with inputs, outputs, checksums,
per-step errors and timestamps. This is the single source of truth for the
``registry/history`` requirement and never stores credentials.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS job_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type      TEXT NOT NULL,
    status        TEXT NOT NULL,
    title         TEXT NOT NULL,
    language      TEXT NOT NULL,
    input_path    TEXT NOT NULL,
    output_path   TEXT NOT NULL,
    checksum_input TEXT,
    checksum_output TEXT,
    errors        TEXT,
    step          TEXT,
    started_at    TEXT,
    finished_at   TEXT,
    metadata      TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Registry:
    """Append-only job history backed by SQLite."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else Path.home() / ".ultron_voice" / "history.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # -- internal ---------------------------------------------------------
    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        if d.get("metadata"):
            try:
                d["metadata"] = json.loads(d["metadata"])
            except json.JSONDecodeError:
                d["metadata"] = {}
        return d

    # -- public -----------------------------------------------------------
    def record(
        self,
        job_type: str,
        status: str,
        title: str,
        language: str,
        input_path: str,
        output_path: str,
        checksum_input: str | None,
        checksum_output: str | None,
        errors: str | None,
        step: str | None,
        started_at: str,
        finished_at: str | None,
        metadata: dict | None = None,
    ) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO job_history
                (job_type, status, title, language, input_path, output_path,
                 checksum_input, checksum_output, errors, step, started_at,
                 finished_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_type, status, title, language, input_path, output_path,
                checksum_input, checksum_output, errors, step, started_at,
                finished_at, json.dumps(metadata or {}),
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    def get(self, entry_id: int) -> dict | None:
        row = self._conn.execute("SELECT * FROM job_history WHERE id = ?", (entry_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def list_jobs(self, job_type: str | None = None) -> list[dict]:
        if job_type:
            rows = self._conn.execute(
                "SELECT * FROM job_history WHERE job_type = ? ORDER BY id", (job_type,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM job_history ORDER BY id DESC").fetchall()
        return [self._row_to_dict(r) for r in rows]

    def latest(self, job_type: str) -> dict | None:
        rows = self._conn.execute(
            "SELECT * FROM job_history WHERE job_type = ? ORDER BY id DESC LIMIT 1",
            (job_type,),
        ).fetchone()
        return self._row_to_dict(rows) if rows else None

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Registry":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
