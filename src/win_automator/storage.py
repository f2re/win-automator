from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional


def data_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(root) / "WinAutomator"
    path.mkdir(parents=True, exist_ok=True)
    return path


class CheckpointDB:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or (data_dir() / "state.sqlite3")
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                excel_path TEXT NOT NULL,
                sheet TEXT NOT NULL,
                scenario_name TEXT NOT NULL,
                next_row INTEGER NOT NULL DEFAULT 0,
                total_rows INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'running',
                error TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()

    def create_job(self, excel_path: str, sheet: str, scenario_name: str, total_rows: int) -> int:
        cursor = self.conn.execute(
            "INSERT INTO jobs(excel_path, sheet, scenario_name, total_rows) VALUES(?,?,?,?)",
            (excel_path, sheet, scenario_name, total_rows),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def update(self, job_id: int, next_row: int, status: str = "running", error: str = "") -> None:
        self.conn.execute(
            "UPDATE jobs SET next_row=?, status=?, error=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (next_row, status, error, job_id),
        )
        self.conn.commit()

    def latest_incomplete(self, excel_path: str, sheet: str, scenario_name: str):
        cur = self.conn.execute(
            """
            SELECT id, next_row, total_rows, status, error
              FROM jobs
             WHERE excel_path=? AND sheet=? AND scenario_name=? AND status IN ('running','error','stopped')
             ORDER BY id DESC LIMIT 1
            """,
            (excel_path, sheet, scenario_name),
        )
        return cur.fetchone()
