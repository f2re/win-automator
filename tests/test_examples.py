from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from win_automator.excel_source import ExcelSource
from win_automator.models import Scenario


def test_employee_entry_example_is_loadable():
    example = ROOT / "examples" / "employee-entry"
    scenario = Scenario.load(example / "scenario.json")
    assert scenario.version == 1
    assert len(scenario.steps) >= 4
    assert any(step.action == "select" for step in scenario.steps)

    source = ExcelSource(example / "sample-data.xlsx")
    try:
        assert "Employees" in source.sheets
        headers, rows = source.read("Employees")
        assert headers == ["ФИО", "Дата рождения", "Отдел", "Должность"]
        assert len(rows) >= 3
    finally:
        source.close()
