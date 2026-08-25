from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from .debug_capture import DebugSink
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
    replacements = {"{": "{{}", "}": "{}}", "+": "{+}", "^": "{^}", "%": "{%}", "~": "{~}", "(": "{(}", ")": "{)}"}
    return "".join(replacements.get(ch, ch) for ch in text)


@dataclass
class RunResult:
    ok: bool
    completed_steps: int
    error: Optional[Exception] = None


class Executor:
    def __init__(
        self,
        on_step: Optional[Callable[[int, Step], None]] = None,
        debug_sink: Optional[DebugSink] = None,
    ) -> None:
        self.on_step = on_step
        self.debug = debug_sink if debug_sink is not None else DebugSink.from_environment("executor")

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
            return True
        return normalize(actual) == normalize(expected)

    def _set_value(self, wrapper, value: Any) -> str:
        text = "" if value is None else str(value)
        try:
            wrapper.set_edit_text(text)
            if self._value_matches(wrapper, text):
                return "set_edit_text"
        except Exception:
            pass
        try:
            wrapper.set_text(text)
            if self._value_matches(wrapper, text):
                return "set_text"
        except Exception:
            pass
        wrapper.click_input()
        from pywinauto.keyboard import send_keys

        send_keys("^a{BACKSPACE}" + _escape_send_keys(text), with_spaces=True, pause=0.01)
        if not self._value_matches(wrapper, text):
            raise RuntimeError("Поле не приняло значение '{}'".format(text))
        return "send_keys"

    def _select(self, wrapper, value: Any) -> str:
        text = "" if value is None else str(value)
        try:
            wrapper.select(text)
            return "wrapper.select"
        except Exception:
            pass
        try:
            wrapper.expand()
            for item in wrapper.descendants(control_type="ListItem"):
                if item.window_text().strip().casefold() == text.strip().casefold():
                    try:
                        item.select()
                        return "expand+listitem.select"
                    except Exception:
                        item.click_input()
                        return "expand+listitem.click_input"
        except Exception:
            pass
        raise RuntimeError("В списке не найдено значение '{}'".format(text))

    @staticmethod
    def _click(wrapper) -> str:
        # InvokePattern may remain blocked until a modal ShowDialog closes. A
        # physical click returns after dispatch and lets the next scenario step
        # resolve controls inside the newly opened dialog.
        try:
            wrapper.click_input()
            return "click_input"
        except Exception:
            wrapper.invoke()
            return "invoke"

    def execute_step(
        self,
        scenario: Scenario,
        step: Step,
        row: Dict[str, Any],
        index: int = -1,
    ) -> str:
        action = step.action.casefold()
        if action == "start_app":
            command = self._mapped_value(scenario, step, row)
            subprocess.Popen(str(command), shell=True)
            return "subprocess.Popen"
        if action == "key":
            from pywinauto.keyboard import send_keys

            send_keys(step.key, pause=0.03)
            return "send_keys"
        if step.target is None:
            raise ValueError("Для действия '{}' не задан элемент".format(step.action))

        callback = None
        if self.debug:
            callback = lambda diagnostic: self.debug.record_resolver(index, diagnostic)
        wrapper = resolve(step.target, timeout=step.timeout, diagnostic_callback=callback)
        try:
            wrapper.set_focus()
            focus_method = "set_focus+"
        except Exception:
            focus_method = ""

        if action == "click":
            return focus_method + self._click(wrapper)
        if action == "double_click":
            wrapper.double_click_input()
            return focus_method + "double_click_input"
        if action == "set_value":
            return focus_method + self._set_value(wrapper, self._mapped_value(scenario, step, row))
        if action == "select":
            return focus_method + self._select(wrapper, self._mapped_value(scenario, step, row))
        if action == "close_window":
            wrapper.top_level_parent().close()
            return "top_level_parent.close"
        raise ValueError("Неизвестное действие '{}'".format(step.action))

    def run(self, scenario: Scenario, row: Dict[str, Any]) -> RunResult:
        if self.debug:
            self.debug.log(
                "executor_run_start",
                scenario=self.debug.sanitize_scenario(scenario),
                row_columns=list(row.keys()),
                step_count=len(scenario.steps),
            )
        for index, step in enumerate(scenario.steps):
            started = time.monotonic()
            try:
                if self.on_step:
                    self.on_step(index, step)
                if self.debug:
                    self.debug.record_executor_step("start", index, step)
                method = self.execute_step(scenario, step, row, index=index)
                if self.debug:
                    self.debug.record_executor_step(
                        "success", index, step, method=method,
                        duration_ms=int((time.monotonic() - started) * 1000),
                    )
            except Exception as exc:
                error = StepExecutionError(index, step, exc)
                if self.debug:
                    self.debug.record_executor_step(
                        "error", index, step,
                        duration_ms=int((time.monotonic() - started) * 1000),
                        error=str(error),
                    )
                    self.debug.log("executor_run_error", completed_steps=index, error=str(error))
                return RunResult(False, index, error)
        if self.debug:
            self.debug.log("executor_run_success", completed_steps=len(scenario.steps))
        return RunResult(True, len(scenario.steps))
