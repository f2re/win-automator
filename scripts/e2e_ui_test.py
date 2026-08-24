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

from win_automator.executor import Executor
from win_automator.inspector import selector_from_wrapper
from win_automator.models import Scenario, Step, ValueSpec


def _name(wrapper) -> str:
    try:
        value = wrapper.window_text()
        if value:
            return str(value)
    except Exception:
        pass
    return str(getattr(wrapper.element_info, "name", "") or "")


def _find(window, control_type: str, name: str):
    wanted = name.strip().casefold()
    for wrapper in window.descendants(control_type=control_type):
        if _name(wrapper).strip().casefold() == wanted:
            return wrapper
    raise RuntimeError("Control not found: {} {!r}".format(control_type, name))


def main() -> int:
    if os.name != "nt":
        print("SKIP: Windows-only UIA e2e test")
        return 0

    from pywinauto import Desktop

    with tempfile.TemporaryDirectory(prefix="win-automator-e2e-") as tmp:
        result_path = Path(tmp) / "result.json"
        env = os.environ.copy()
        env["WIN_AUTOMATOR_E2E_RESULT"] = str(result_path)
        target = ROOT / "scripts" / "TargetForm.ps1"
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
            window = desktop.window(title="Карточка сотрудника — тест Win Automator")
            window.wait("exists enabled visible ready", timeout=15)
            top = window.wrapper_object()

            fields = {
                "ФИО": _find(top, "Edit", "ФИО"),
                "Дата рождения": _find(top, "Edit", "Дата рождения"),
                "Отдел": _find(top, "ComboBox", "Отдел"),
                "Должность": _find(top, "Edit", "Должность"),
                "Сохранить": _find(top, "Button", "Сохранить"),
            }

            scenario = Scenario(
                name="UIA E2E",
                steps=[
                    Step(
                        action="set_value",
                        target=selector_from_wrapper(fields["ФИО"], "uia"),
                        value=ValueSpec(source="excel", column="ФИО"),
                    ),
                    Step(
                        action="set_value",
                        target=selector_from_wrapper(fields["Дата рождения"], "uia"),
                        value=ValueSpec(source="excel", column="Дата рождения"),
                    ),
                    Step(
                        action="select",
                        target=selector_from_wrapper(fields["Отдел"], "uia"),
                        value=ValueSpec(source="excel", column="Отдел"),
                    ),
                    Step(
                        action="set_value",
                        target=selector_from_wrapper(fields["Должность"], "uia"),
                        value=ValueSpec(source="excel", column="Должность"),
                    ),
                    Step(
                        action="click",
                        target=selector_from_wrapper(fields["Сохранить"], "uia"),
                    ),
                ],
            )
            row = {
                "ФИО": "Иванов Иван Иванович",
                "Дата рождения": "01.08.2000",
                "Отдел": "ОМН",
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

            proc.wait(timeout=10)
            if proc.returncode != 0:
                raise RuntimeError("TargetForm exited with code {}".format(proc.returncode))
            print("UIA E2E OK: form filled, ComboBox selected and Save invoked")
            return 0
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
