from __future__ import annotations

import importlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Callable, List, Tuple


def _check(name: str, callback: Callable[[], None], results: List[Tuple[str, bool, str]]) -> None:
    try:
        callback()
        results.append((name, True, ""))
    except Exception as exc:
        results.append((name, False, "{}: {}".format(type(exc).__name__, exc)))


def run_smoke_test(gui: bool = False) -> int:
    """Validate the packaged runtime without network or external test data."""
    results: List[Tuple[str, bool, str]] = []

    for module in ("tkinter", "openpyxl", "pywinauto", "pynput", "comtypes", "win32api"):
        _check("import:{}".format(module), lambda module=module: importlib.import_module(module), results)

    def tcl_test() -> None:
        import tkinter

        interp = tkinter.Tcl()
        version = interp.eval("info patchlevel")
        if not version:
            raise RuntimeError("Tcl runtime unavailable")

    _check("tcl", tcl_test, results)

    def win32_test() -> None:
        import win32api

        win32api.GetVersionEx()

    _check("win32", win32_test, results)

    def uia_test() -> None:
        from pywinauto import Desktop
        from pywinauto.controls.uiawrapper import UIAWrapper  # noqa: F401

        # Creating the UIA backend loads the packaged comtypes/UIAutomationCore
        # stack. Do not enumerate the entire service-session desktop here:
        # that can block on unrelated shell windows. Actual element discovery,
        # editing, ComboBox selection and Invoke are verified by e2e_ui_test.py.
        desktop = Desktop(backend="uia")
        if getattr(desktop, "backend", None) is None:
            raise RuntimeError("UIA backend was not initialized")

    _check("uia-backend", uia_test, results)

    with tempfile.TemporaryDirectory(prefix="win-automator-smoke-") as tmp:
        root = Path(tmp)

        def sqlite_test() -> None:
            path = root / "state.sqlite3"
            conn = sqlite3.connect(str(path))
            try:
                conn.execute("create table smoke(v integer)")
                conn.execute("insert into smoke values(7)")
                conn.commit()
                if conn.execute("select v from smoke").fetchone()[0] != 7:
                    raise RuntimeError("SQLite roundtrip failed")
            finally:
                conn.close()

        _check("sqlite", sqlite_test, results)

        def xlsx_test() -> None:
            from openpyxl import Workbook, load_workbook

            path = root / "smoke.xlsx"
            wb = Workbook()
            ws = wb.active
            ws.append(["ФИО", "Отдел"])
            ws.append(["Иванов И.И.", "ОМН"])
            wb.save(str(path))
            wb.close()
            loaded = load_workbook(str(path), read_only=True, data_only=True)
            try:
                if loaded.active["A2"].value != "Иванов И.И.":
                    raise RuntimeError("XLSX roundtrip failed")
            finally:
                loaded.close()

        _check("xlsx", xlsx_test, results)

        def scenario_test() -> None:
            from .models import Scenario, Step, ValueSpec

            path = root / "scenario.json"
            scenario = Scenario(name="smoke", steps=[Step(action="key", key="{ENTER}", value=ValueSpec(literal=""))])
            scenario.save(path)
            loaded = Scenario.load(path)
            if loaded.name != "smoke" or len(loaded.steps) != 1:
                raise RuntimeError("Scenario serialization failed")

        _check("scenario", scenario_test, results)

        def checkpoint_test() -> None:
            from .storage import CheckpointDB

            db = CheckpointDB(root / "checkpoint.sqlite3")
            db.create_job("sample.xlsx", "Sheet1", "smoke", 2)
            row = db.latest_incomplete("sample.xlsx", "Sheet1", "smoke")
            if not row:
                raise RuntimeError("Checkpoint roundtrip failed")
            db.conn.close()

        _check("checkpoint", checkpoint_test, results)

        if gui:
            def gui_test() -> None:
                old_local = os.environ.get("LOCALAPPDATA")
                os.environ["LOCALAPPDATA"] = str(root / "appdata")
                try:
                    from .ui import App

                    app = App()
                    app.withdraw()
                    app.update_idletasks()
                    app.update()
                    try:
                        app.db.conn.close()
                    except Exception:
                        pass
                    app.destroy()
                finally:
                    if old_local is None:
                        os.environ.pop("LOCALAPPDATA", None)
                    else:
                        os.environ["LOCALAPPDATA"] = old_local

            _check("gui", gui_test, results)

    failed = [item for item in results if not item[1]]
    report = {
        "ok": not failed,
        "checks": [{"name": n, "ok": ok, "error": err} for n, ok, err in results],
    }
    try:
        print(json.dumps(report, ensure_ascii=False))
    except Exception:
        pass
    return 0 if not failed else 2
