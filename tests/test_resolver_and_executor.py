import datetime as dt
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from win_automator.executor import Executor
from win_automator.inspector import score_wrapper
from win_automator.models import Scenario, Selector, Step, ValueSpec


class Rect:
    def __init__(self, left, top, right, bottom):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom

    def width(self):
        return self.right - self.left

    def height(self):
        return self.bottom - self.top


class Wrapper:
    def __init__(self, rect, top_rect, name="", automation_id="", control_id=None):
        self._rect = rect
        self._top = SimpleNamespace(rectangle=lambda: top_rect)
        self.element_info = SimpleNamespace(
            automation_id=automation_id,
            control_type="Edit",
            class_name="EditClass",
            control_id=control_id,
            name=name,
        )

    def rectangle(self):
        return self._rect

    def top_level_parent(self):
        return self._top

    def parent(self):
        return SimpleNamespace(window_text=lambda: "Панель")

    def window_text(self):
        return self.element_info.name


def test_relative_position_disambiguates_similar_controls():
    top = Rect(0, 0, 1000, 1000)
    expected = Wrapper(Rect(100, 180, 300, 220), top)
    wrong = Wrapper(Rect(100, 720, 300, 760), top)
    selector = Selector(
        control_type="Edit",
        class_name="EditClass",
        parent_name="Панель",
        relative_x=0.20,
        relative_y=0.20,
    )
    assert score_wrapper(expected, selector) > score_wrapper(wrong, selector) + 30


def test_executor_formats_excel_value_like_training_sample():
    scenario = Scenario()
    date_step = Step(
        action="set_value",
        value=ValueSpec(source="excel", column="Дата", literal="01.02.2020"),
    )
    code_step = Step(
        action="set_value",
        value=ValueSpec(source="excel", column="Код", literal="0007"),
    )
    row = {"Дата": dt.date(2026, 8, 24), "Код": 12}
    assert Executor._mapped_value(scenario, date_step, row) == "24.08.2026"
    assert Executor._mapped_value(scenario, code_step, row) == "0012"


def test_click_prefers_nonblocking_physical_click():
    calls = []

    class ClickWrapper:
        def click_input(self):
            calls.append("click_input")

        def invoke(self):
            calls.append("invoke")
            raise AssertionError("invoke should not be used when click_input works")

    Executor._click(ClickWrapper())
    assert calls == ["click_input"]
