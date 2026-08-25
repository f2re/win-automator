import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from win_automator.models import Selector
from win_automator.recorder import SemanticRecorder
from win_automator.storage import CheckpointDB, excel_fingerprint


def test_recorder_rebinds_target_after_keyboard_navigation(monkeypatch):
    first = Selector(name="ФИО", automation_id="txtName", control_type="Edit")
    second = Selector(name="Город", automation_id="txtCity", control_type="Edit")
    values = {"txtName": "Иванов", "txtCity": "Москва"}

    recorder = SemanticRecorder({"ФИО": "Иванов", "Город": "Москва"})
    recorder.running = True
    recorder._active_target = first
    recorder._text_dirty = True
    monkeypatch.setattr(recorder, "_read_target_value", lambda target: values[target.automation_id])
    recorder._flush_text()

    # This is the state immediately after Tab: the previous target is discarded.
    recorder._active_target = None
    monkeypatch.setattr("win_automator.recorder.inspect_focused", lambda: second)
    recorder._mark_text_change("М")
    recorder._flush_text()

    assert [step.value.column for step in recorder.steps] == ["ФИО", "Город"]
    assert [step.target.automation_id for step in recorder.steps] == ["txtName", "txtCity"]


def test_checkpoint_db_migrates_old_schema_and_rejects_changed_workbook(tmp_path):
    db_path = tmp_path / "state.sqlite3"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE jobs (
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
    conn.commit()
    conn.close()

    db = CheckpointDB(db_path)
    columns = {row[1] for row in db.conn.execute("PRAGMA table_info(jobs)")}
    assert "excel_fingerprint" in columns

    workbook = tmp_path / "data.xlsx"
    workbook.write_bytes(b"version-one")
    fingerprint_one = excel_fingerprint(workbook)
    job_id = db.create_job(str(workbook), "Лист1", "Сценарий", 10, fingerprint=fingerprint_one)
    db.update(job_id, 4, status="error", error="test")
    assert db.latest_incomplete(str(workbook), "Лист1", "Сценарий", fingerprint_one)[1] == 4

    workbook.write_bytes(b"version-two")
    fingerprint_two = excel_fingerprint(workbook)
    assert fingerprint_two != fingerprint_one
    assert db.latest_incomplete(str(workbook), "Лист1", "Сценарий", fingerprint_two) is None
