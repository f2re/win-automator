from __future__ import annotations

import threading
from typing import Callable, Dict, List, Optional

from .debug_capture import DebugSink
from .excel_source import infer_column
from .inspector import inspect_focused, inspect_point, resolve
from .models import Scenario, Step, ValueSpec


class SemanticRecorder:
    """Small recorder that converts raw input into semantic RPA steps.

    F8 pauses/resumes. F9 finishes recording.
    """

    def __init__(
        self,
        row: Dict[str, object],
        on_step: Optional[Callable[[Step], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
        debug_sink: Optional[DebugSink] = None,
    ) -> None:
        self.row = row
        self.on_step = on_step
        self.on_stop = on_stop
        self.debug = debug_sink if debug_sink is not None else DebugSink.from_environment("recorder")
        self.steps: List[Step] = []
        self.paused = False
        self.running = False
        self._mouse_listener = None
        self._keyboard_listener = None
        self._text_buffer: List[str] = []
        self._active_target = None
        self._pending_combo = None
        self._text_dirty = False
        self._lock = threading.RLock()

    def _append(self, step: Step) -> None:
        self.steps.append(step)
        if self.debug:
            self.debug.record_semantic_step(step, origin="recorder")
        if self.on_step:
            self.on_step(step)

    def _value_spec(self, value: object, target=None) -> ValueSpec:
        hints = []
        if target:
            hints.extend((target.name, target.automation_id, target.parent_name))
        column = infer_column(value, self.row, hints=hints)
        if self.debug:
            self.debug.log(
                "recorder_value_mapping",
                matching_column=column or "",
                matched=bool(column),
                value_length=len(str(value or "")),
            )
        if column:
            return ValueSpec(source="excel", column=column, literal=value)
        return ValueSpec(source="literal", literal=value)

    @staticmethod
    def _read_wrapper_value(wrapper):
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

    def _read_target_value(self, target):
        try:
            wrapper = resolve(target, timeout=0.8)
            return self._read_wrapper_value(wrapper)
        except Exception:
            return None

    def _activate_focused_target(self) -> None:
        if self._active_target is not None:
            return
        try:
            target = inspect_focused()
        except Exception as exc:
            if self.debug:
                self.debug.log("recorder_focus_inspect_error", error=str(exc))
            return
        if (target.control_type or "").casefold() in ("edit", "document"):
            self._active_target = target
            self._pending_combo = None

    def _flush_text(self) -> None:
        with self._lock:
            target = self._active_target
            dirty = self._text_dirty
            buffered = "".join(self._text_buffer)
            self._text_buffer = []
            self._text_dirty = False
        if not target or not dirty:
            return
        final_value = self._read_target_value(target)
        if final_value is None:
            final_value = buffered
        self._append(
            Step(
                action="set_value",
                target=target,
                value=self._value_spec(final_value, target=target),
                description="Заполнить {}".format(target.name or "поле"),
            )
        )

    def _on_click(self, x, y, button, pressed):
        if not self.running or self.paused or not pressed:
            return
        try:
            from pynput.mouse import Button
            if button != Button.left:
                return
        except Exception:
            pass
        try:
            target = inspect_point(int(x), int(y))
            if self.debug:
                self.debug.log("recorder_inspect", x=int(x), y=int(y), target=self.debug._redact_selector(target))
        except Exception as exc:
            if self.debug:
                self.debug.log("recorder_inspect_error", x=int(x), y=int(y), error=str(exc))
            return

        self._flush_text()
        control_type = (target.control_type or "").casefold()
        if control_type in ("edit", "document"):
            self._active_target = target
            self._pending_combo = None
            self._text_dirty = False
            return
        if control_type in ("combobox", "combo box"):
            self._active_target = None
            self._pending_combo = target
            return
        if control_type in ("listitem", "list item") and self._pending_combo:
            value = target.name
            self._append(
                Step(
                    action="select",
                    target=self._pending_combo,
                    value=self._value_spec(value, target=self._pending_combo),
                    description="Выбрать {}".format(self._pending_combo.name or "значение"),
                )
            )
            self._pending_combo = None
            return

        self._active_target = None
        self._pending_combo = None
        self._append(
            Step(action="click", target=target,
                 description="Нажать {}".format(target.name or target.control_type or "элемент"))
        )

    def _mark_text_change(self, char: Optional[str] = None) -> None:
        self._activate_focused_target()
        if not self._active_target:
            return
        with self._lock:
            self._text_dirty = True
            if char and char.isprintable():
                self._text_buffer.append(char)

    def _on_press(self, key):
        if not self.running:
            return False
        from pynput.keyboard import Key

        if key == Key.f8:
            self.paused = not self.paused
            if self.debug:
                self.debug.log("recorder_pause", paused=self.paused)
            return
        if key == Key.f9:
            if self.debug:
                self.debug.log("recorder_finish_hotkey")
            self.stop()
            return False
        if self.paused:
            return

        if key == Key.tab:
            self._flush_text()
            # Focus moves after this callback; never keep the old text target.
            self._active_target = None
            self._pending_combo = None
            return
        if key in (Key.enter, Key.esc):
            self._flush_text()
            self._active_target = None
            self._append(
                Step(
                    action="key",
                    key="{ENTER}" if key == Key.enter else "{ESC}",
                    description="Нажать Enter" if key == Key.enter else "Нажать Esc",
                )
            )
            return
        if key in (Key.backspace, Key.delete):
            self._mark_text_change()
            with self._lock:
                if key == Key.backspace and self._text_buffer:
                    self._text_buffer.pop()
            return
        try:
            char = key.char
        except AttributeError:
            char = None
        if char:
            # Ctrl+V/Ctrl+A may surface as a control character. Dirty state is
            # enough: flush reads the final UIA value instead of trusting keys.
            self._mark_text_change(char if char.isprintable() else None)

    def start(self) -> None:
        if self.running:
            return
        from pynput import keyboard, mouse

        self.running = True
        if self.debug:
            self.debug.log("recorder_start", row_columns=list(self.row.keys()))
        self._mouse_listener = mouse.Listener(on_click=self._on_click)
        self._keyboard_listener = keyboard.Listener(on_press=self._on_press)
        self._mouse_listener.start()
        self._keyboard_listener.start()

    def stop(self) -> Scenario:
        if not self.running:
            return Scenario(steps=list(self.steps))
        self._flush_text()
        self.running = False
        try:
            if self._mouse_listener:
                self._mouse_listener.stop()
            if self._keyboard_listener:
                self._keyboard_listener.stop()
        finally:
            if self.debug:
                self.debug.log("recorder_stop", step_count=len(self.steps))
            if self.on_stop:
                self.on_stop()
        return Scenario(steps=list(self.steps))
