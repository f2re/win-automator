from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from win_automator.models import Scenario, Selector, Step, ValueSpec


def test_scenario_roundtrip(tmp_path):
    scenario = Scenario(
        name="Тест",
        steps=[
            Step(
                action="set_value",
                target=Selector(name="ФИО", control_type="Edit", automation_id="txtName"),
                value=ValueSpec(source="excel", column="ФИО"),
            )
        ],
    )
    path = tmp_path / "scenario.json"
    scenario.save(path)
    loaded = Scenario.load(path)
    assert loaded.name == "Тест"
    assert loaded.steps[0].target.automation_id == "txtName"
    assert loaded.steps[0].value.column == "ФИО"
