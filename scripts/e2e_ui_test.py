from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from win_automator.debug_capture import ACTIVE_MARKER, ENV_DEBUG_DIR, ENV_DEBUG_VALUES
from win_automator.executor import Executor
from win_automator.inspector import selector_from_wrapper
from win_automator.models import Scenario, Step, ValueSpec


def _find_by_id(window, automation_id: str, control_type: str):
    for wrapper in window.descendants(control_type=control_type):
        info = wrapper.element_info
        if str(getattr(info, "automation_id", "") or "") == automation_id:
            return wrapper
    raise RuntimeError("Control not found: {} / {}".format(control_type, automation_id))


def main() -> int:
    if os.name != "nt":
        print("SKIP: Windows-only UIA e2e test")
        return 0

    from pywinauto import Desktop

    with tempfile.TemporaryDirectory(prefix="win-automator-e2e-") as tmp:
        tmp_root = Path(tmp)
        result_path = tmp_root / "result.json"
        debug_root = tmp_root / "debug"
        debug_root.mkdir()
        (debug_root / ACTIVE_MARKER).write_text("e2e", encoding="utf-8")
        old_debug_dir = os.environ.get(ENV_DEBUG_DIR)
        old_debug_values = os.environ.get(ENV_DEBUG_VALUES)
        os.environ[ENV_DEBUG_DIR] = str(debug_root)
        os.environ[ENV_DEBUG_VALUES] = "0"

        env = os.environ.copy()
        env["WIN_AUTOMATOR_E2E_RESULT"] = str(result_path)
        target = ROOT / "scripts" / "E2ETargetForm.ps1"
        proc = subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(target),
            ],
            env=env,
        )
        try:
            desktop = Desktop(backend="uia")
            window = desktop.window(title="Win Automator E2E Target")
            window.wait("exists enabled visible ready", timeout=15)
            top = window.wrapper_object()

            full_name = _find_by_id(top, "txtFullName", "Edit")
            birth_date = _find_by_id(top, "txtBirthDate", "Edit")
            department = _find_by_id(top, "cmbDepartment", "ComboBox")
            position = _find_by_id(top, "txtPosition", "Edit")
            save = _find_by_id(top, "btnSave", "Button")

            scenario = Scenario(
                name="UIA E2E",
                steps=[
                    Step(
                        action="set_value",
                        target=selector_from_wrapper(full_name, "uia"),
                        value=ValueSpec(source="excel", column="ФИО"),
                    ),
                    Step(
                        action="set_value",
                        target=selector_from_wrapper(birth_date, "uia"),
                        value=ValueSpec(source="excel", column="Дата рождения"),
                    ),
                    Step(
                        action="select",
                        target=selector_from_wrapper(department, "uia"),
                        value=ValueSpec(source="excel", column="Отдел"),
                    ),
                    Step(
                        action="set_value",
                        target=selector_from_wrapper(position, "uia"),
                        value=ValueSpec(source="excel", column="Должность"),
                    ),
                    Step(action="click", target=selector_from_wrapper(save, "uia")),
                ],
            )
            row = {
                "ФИО": "Иванов Иван Иванович",
                "Дата рождения": "01.08.2000",
                "Отдел": "OMN",
                "Должность": "Инженер-метеоролог",
            }
            result = Executor().run(scenario, row)
            if not result.ok:
                raise RuntimeError(str(result.error))

            deadline = time.time() + 10
            while time.time() < deadline and not result_path.exists():
                time.sleep(0.1)
            if not result_path.exists():
                raise RuntimeError("Target form did not write the result file")

            data = json.loads(result_path.read_text(encoding="utf-8-sig"))
            expected = {
                "full_name": row["ФИО"],
                "birth_date": row["Дата рождения"],
                "department": row["Отдел"],
                "position": row["Должность"],
            }
            if data != expected:
                raise AssertionError("UIA roundtrip mismatch: {!r} != {!r}".format(data, expected))

            event_files = list(debug_root.glob("events-executor-*.jsonl"))
            if len(event_files) != 1:
                raise AssertionError("Expected one executor debug event file, got {}".format(event_files))
            debug_text = event_files[0].read_text(encoding="utf-8")
            for required in ("executor_run_start", "resolver", "executor_step", "executor_run_success"):
                if '"type":"{}"'.format(required) not in debug_text:
                    raise AssertionError("Debug trace missing event type: {}".format(required))
            if row["ФИО"] in debug_text or row["Должность"] in debug_text:
                raise AssertionError("Debug trace leaked field values while redaction was enabled")

            proc.wait(timeout=10)
            if proc.returncode != 0:
                raise RuntimeError("E2ETargetForm exited with code {}".format(proc.returncode))
            print("UIA E2E OK: actions executed and structured debug trace captured")
            return 0
        finally:
            if old_debug_dir is None:
                os.environ.pop(ENV_DEBUG_DIR, None)
            else:
                os.environ[ENV_DEBUG_DIR] = old_debug_dir
            if old_debug_values is None:
                os.environ.pop(ENV_DEBUG_VALUES, None)
            else:
                os.environ[ENV_DEBUG_VALUES] = old_debug_values
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
