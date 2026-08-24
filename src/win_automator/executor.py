from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from .excel_source import format_like_sample, normalize
from .inspector import resolve
from .models import Scenario, Step


class StepExecutionError(RuntimeError):
    def __init__(self, index: int, step: Step, cause: Exception) -> None:
        self.index = index
        self.step = step
        self.cause = cause
        super().__init__("Шаг {}: {}: {}".format(index + 1, step.description or step.action, cause))


def _escape_send_keys(text: str) -> str:
    replacements = {
        "{": "{{}",
        "}": "{}}",
        "+": "{+}",
        "^": "{^}",
        "%": "{%}",
        "~": "{~}",
        "(": "{(}",
        ")": "{)}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


@dataclass
class RunResult:
    ok: bool
    completed_steps: int
    error: Optional[Exception] = None


class Executor:
    def __init__(self, on_step: Optional[Callable[[int, Step], None]] = None) -> None:
        self.on_step = on_step

    @staticmethod
    def _mapped_value(scenario: Scenario, step: Step, row: Dict[str, Any]) -> Any:
        if not step.value:
            return ""
        value = step.value.resolve(row)
        if step.value.source == "excel":
            mapping = scenario.mappings.get(step.value.column, {})
            mapped = mapping.get(str(value))
            if mapped is not None:
                return mapped
            return format_like_sample(value, step.value.literal)
        return value

    @staticmethod
    def _read_value(wrapper):
        for getter_name in ("get_value", "window_text"):
            try:
                getter = getattr(wrapper, getter_name)
                value = getter() if callable(getter) else getter
                if value is not None:
                    return value
            except Exception:
                pass
        try:
            texts = wrapper.texts()
            if texts:
                return texts[0]
        except Exception:
            pass
        return None

    def _value_matches(self, wrapper, expected: str) -> bool:
        actual = self._read_value(wrapper)
        if actual is None:
            return True  # control does not expose a readable value; do not false-fail
        return normalize(actual) == normalize(expected)

    def _set_value(self, wrapper, value: Any) -> None:
        text = "" if value is None else str(value)
        try:
            wrapper.set_edit_text(text)
            if self._value_matches(wrapper, text):
                return
        except Exception:
            pass
        try:
            wrapper.set_text(text)
            if self._value_matches(wrapper, text):
                return
        except Exception:
            pass
        wrapper.click_input()
        from pywinauto.keyboard import send_keys

        send_keys("^a{BACKSPACE}" + _escape_send_keys(text), with_spaces=True, pause=0.01)
        if not self._value_matches(wrapper, text):
            raise RuntimeError("Поле не приняло значение '{}'".format(text))

    def _select(self, wrapper, value: Any) -> None:
        text = "" if value is None else str(value)
        try:
            wrapper.select(text)
            return
        except Exception:
            pass
        try:
            wrapper.expand()
            for item in wrapper.descendants(control_type="ListItem"):
                if item.window_text().strip().casefold() == text.strip().casefold():
                    try:
                        item.select()
                    except Exception:
                        item.click_input()
                    return
        except Exception:
            pass
        raise RuntimeError("В списке не найдено значение '{}'".format(text))

    @staticmethod
    def _click(wrapper) -> None:
        # click_input returns after the physical click even if the handler opens a
        # modal dialog. InvokePattern can stay blocked until ShowDialog returns,
        # which would deadlock the following scenario step.
        try:
            wrapper.click_input()
            return
        except Exception:
            pass
        wrapper.invoke()

    def execute_step(self, scenario: Scenario, step: Step, row: Dict[str, Any]) -> None:
        action = step.action.casefold()
        if action == "start_app":
            command = self._mapped_value(scenario, step, row)
            subprocess.Popen(str(command), shell=True)
            return
        if action == "key":
            from pywinauto.keyboard import send_keys

            send_keys(step.key, pause=0.03)
            return
        if step.target is None:
            raise ValueError("Для действия '{}' не задан элемент".format(step.action))

        wrapper = resolve(step.target, timeout=step.timeout)
        try:
            wrapper.set_focus()
        except Exception:
            pass

        if action == "click":
            self._click(wrapper)
        elif action == "double_click":
            wrapper.double_click_input()
        elif action == "set_value":
            self._set_value(wrapper, self._mapped_value(scenario, step, row))
        elif action == "select":
            self._select(wrapper, self._mapped_value(scenario, step, row))
        elif action == "close_window":
            wrapper.top_level_parent().close()
        else:
            raise ValueError("Неизвестное действие '{}'".format(step.action))

    def run(self, scenario: Scenario, row: Dict[str, Any]) -> RunResult:
        for index, step in enumerate(scenario.steps):
            try:
                if self.on_step:
                    self.on_step(index, step)
                self.execute_step(scenario, step, row)
            except Exception as exc:
                return RunResult(False, index, StepExecutionError(index, step, exc))
        return RunResult(True, len(scenario.steps))
