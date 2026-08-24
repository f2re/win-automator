from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from .models import Selector


class AmbiguousElementError(RuntimeError):
    pass


@dataclass
class Candidate:
    wrapper: object
    score: float
    control_score: float
    stable_hits: int
    description: str


def _safe(value, default=""):
    try:
        return value() if callable(value) else value
    except Exception:
        return default


def _process_name(pid: int) -> str:
    try:
        import win32api
        import win32con
        import win32process

        handle = win32api.OpenProcess(
            win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
            False,
            pid,
        )
        try:
            return os.path.basename(win32process.GetModuleFileNameEx(handle, 0))
        finally:
            handle.Close()
    except Exception:
        return ""


def selector_from_wrapper(wrapper, backend: str) -> Selector:
    info = wrapper.element_info
    top = wrapper.top_level_parent()
    top_info = top.element_info
    rect = _safe(wrapper.rectangle, None)
    top_rect = _safe(top.rectangle, None)
    rx = ry = None
    if rect is not None and top_rect is not None and top_rect.width() and top_rect.height():
        center_x = (rect.left + rect.right) / 2.0
        center_y = (rect.top + rect.bottom) / 2.0
        rx = (center_x - top_rect.left) / float(top_rect.width())
        ry = (center_y - top_rect.top) / float(top_rect.height())

    parent_name = ""
    try:
        parent = wrapper.parent()
        if parent:
            parent_name = str(_safe(parent.window_text, "") or "")
    except Exception:
        pass

    pid = int(getattr(info, "process_id", 0) or 0)
    return Selector(
        backend=backend,
        window_title=str(_safe(top.window_text, "") or getattr(top_info, "name", "") or ""),
        window_class=str(getattr(top_info, "class_name", "") or ""),
        process_name=_process_name(pid),
        automation_id=str(getattr(info, "automation_id", "") or ""),
        control_type=str(getattr(info, "control_type", "") or ""),
        name=str(_safe(wrapper.window_text, "") or getattr(info, "name", "") or ""),
        class_name=str(getattr(info, "class_name", "") or ""),
        control_id=getattr(info, "control_id", None),
        parent_name=parent_name,
        relative_x=rx,
        relative_y=ry,
    )


def inspect_point(x: int, y: int) -> Selector:
    from pywinauto import Desktop

    errors = []
    for backend in ("uia", "win32"):
        try:
            wrapper = Desktop(backend=backend).from_point(x, y)
            return selector_from_wrapper(wrapper, backend)
        except Exception as exc:
            errors.append("{}: {}".format(backend, exc))
    raise RuntimeError("Не удалось определить элемент под курсором: {}".format("; ".join(errors)))


def inspect_cursor() -> Selector:
    import win32api

    x, y = win32api.GetCursorPos()
    return inspect_point(int(x), int(y))


def inspect_focused() -> Selector:
    """Return the currently focused control, preferring UI Automation."""

    errors = []
    try:
        from pywinauto.controls.uiawrapper import UIAWrapper
        from pywinauto.windows.uia_element_info import UIAElementInfo

        wrapper = UIAWrapper(UIAElementInfo.get_active())
        return selector_from_wrapper(wrapper, "uia")
    except Exception as exc:
        errors.append("uia: {}".format(exc))

    try:
        import win32gui
        from pywinauto.controls.hwndwrapper import HwndWrapper

        hwnd = win32gui.GetForegroundWindow()
        top = HwndWrapper(hwnd)
        try:
            wrapper = top.get_focus()
        except Exception:
            wrapper = top
        return selector_from_wrapper(wrapper, "win32")
    except Exception as exc:
        errors.append("win32: {}".format(exc))
    raise RuntimeError("Не удалось определить активный элемент: {}".format("; ".join(errors)))


def _text(value: object) -> str:
    return str(value or "").strip().casefold()


def _relative_position(wrapper):
    try:
        rect = _safe(wrapper.rectangle, None)
        top_rect = _safe(wrapper.top_level_parent().rectangle, None)
        if rect is None or top_rect is None or not top_rect.width() or not top_rect.height():
            return None
        center_x = (rect.left + rect.right) / 2.0
        center_y = (rect.top + rect.bottom) / 2.0
        return (
            (center_x - top_rect.left) / float(top_rect.width()),
            (center_y - top_rect.top) / float(top_rect.height()),
        )
    except Exception:
        return None


def score_wrapper(wrapper, selector: Selector) -> float:
    """Score a control only; window identity is scored separately in resolve()."""

    info = wrapper.element_info
    score = 0.0
    automation_id = str(getattr(info, "automation_id", "") or "")
    control_type = str(getattr(info, "control_type", "") or "")
    class_name = str(getattr(info, "class_name", "") or "")
    control_id = getattr(info, "control_id", None)
    name = str(_safe(wrapper.window_text, "") or getattr(info, "name", "") or "")

    if selector.automation_id:
        score += 130 if automation_id == selector.automation_id else (-40 if automation_id else 0)
    if selector.control_id is not None:
        score += 120 if control_id == selector.control_id else (-35 if control_id is not None else 0)
    if selector.control_type:
        score += 35 if _text(control_type) == _text(selector.control_type) else -25
    if selector.name:
        if _text(name) == _text(selector.name):
            score += 60
        elif name and (_text(selector.name) in _text(name) or _text(name) in _text(selector.name)):
            score += 18
    if selector.class_name:
        score += 25 if _text(class_name) == _text(selector.class_name) else (-10 if class_name else 0)
    try:
        parent = wrapper.parent()
        if selector.parent_name and parent and _text(parent.window_text()) == _text(selector.parent_name):
            score += 30
    except Exception:
        pass

    if selector.relative_x is not None and selector.relative_y is not None:
        actual = _relative_position(wrapper)
        if actual is not None:
            distance = math.hypot(actual[0] - selector.relative_x, actual[1] - selector.relative_y)
            if distance <= 0.03:
                score += 55
            elif distance <= 0.08:
                score += 42
            elif distance <= 0.15:
                score += 25
            elif distance <= 0.30:
                score += 8
            else:
                score -= 15
    return score


def _stable_hits(wrapper, selector: Selector) -> int:
    info = wrapper.element_info
    hits = 0
    if selector.automation_id and str(getattr(info, "automation_id", "") or "") == selector.automation_id:
        hits += 1
    if selector.control_id is not None and getattr(info, "control_id", None) == selector.control_id:
        hits += 1
    return hits


def _minimum_control_score(selector: Selector, minimum_score: int) -> float:
    # Never accept "same control type" alone. Captured selectors normally have
    # either an id/name or a relative position, so 60 is a safe fallback floor.
    if selector.automation_id or selector.control_id is not None:
        return max(float(minimum_score), 55.0)
    if selector.name or selector.relative_x is not None or selector.relative_y is not None:
        return max(float(minimum_score), 60.0)
    return max(float(minimum_score), 50.0)


def _candidate_description(wrapper) -> str:
    info = wrapper.element_info
    return "{} / {} / {}".format(
        str(_safe(wrapper.window_text, "") or getattr(info, "name", "") or "без имени"),
        str(getattr(info, "control_type", "") or "?"),
        str(getattr(info, "automation_id", "") or getattr(info, "control_id", "") or "без id"),
    )


def resolve(selector: Selector, timeout: float = 10.0, minimum_score: int = 30):
    from pywinauto import Desktop

    deadline = time.time() + max(0.2, timeout)
    last_error = None
    required_control_score = _minimum_control_score(selector, minimum_score)
    while time.time() < deadline:
        try:
            desktop = Desktop(backend=selector.backend or "uia")
            windows = desktop.windows()
            candidates: List[Candidate] = []
            process_cache: Dict[int, str] = {}
            for window in windows:
                try:
                    title = str(_safe(window.window_text, "") or "")
                    win_info = window.element_info
                    title_score = 0.0
                    if selector.window_title:
                        expected_title = _text(selector.window_title)
                        actual_title = _text(title)
                        if expected_title == actual_title:
                            title_score = 30
                        elif expected_title in actual_title or actual_title in expected_title:
                            title_score = 12
                        else:
                            continue

                    class_score = 0.0
                    if selector.window_class:
                        actual_class = str(getattr(win_info, "class_name", "") or "")
                        if actual_class and _text(actual_class) != _text(selector.window_class):
                            continue
                        if actual_class:
                            class_score = 15

                    process_score = 0.0
                    if selector.process_name:
                        pid = int(getattr(win_info, "process_id", 0) or 0)
                        if pid not in process_cache:
                            process_cache[pid] = _process_name(pid) if pid else ""
                        actual_process = process_cache[pid]
                        if actual_process and _text(actual_process) != _text(selector.process_name):
                            continue
                        if actual_process:
                            process_score = 25

                    active_score = 0.0
                    try:
                        if bool(window.is_active()):
                            active_score = 18
                    except Exception:
                        pass
                    window_score = title_score + class_score + process_score + active_score

                    wrappers = [window]
                    try:
                        wrappers.extend(window.descendants())
                    except Exception:
                        pass
                    for wrapper in wrappers:
                        control_score = score_wrapper(wrapper, selector)
                        if control_score < required_control_score:
                            continue
                        candidates.append(
                            Candidate(
                                wrapper=wrapper,
                                score=control_score + window_score,
                                control_score=control_score,
                                stable_hits=_stable_hits(wrapper, selector),
                                description=_candidate_description(wrapper),
                            )
                        )
                except Exception:
                    continue

            candidates.sort(key=lambda item: (item.stable_hits, item.score, item.control_score), reverse=True)
            if candidates:
                best = candidates[0]
                if len(candidates) > 1:
                    second = candidates[1]
                    same_identity_strength = best.stable_hits == second.stable_hits
                    too_close = abs(best.score - second.score) < 8.0
                    if same_identity_strength and too_close:
                        raise AmbiguousElementError(
                            "Найдено несколько почти одинаковых элементов: '{}' и '{}'. "
                            "Укажите элемент заново или добавьте более устойчивый признак.".format(
                                best.description, second.description
                            )
                        )
                return best.wrapper
            last_error = RuntimeError("нет кандидатов с control score >= {:.0f}".format(required_control_score))
        except AmbiguousElementError:
            raise
        except Exception as exc:
            last_error = exc
        time.sleep(0.2)
    raise TimeoutError(
        "Элемент не найден за {:.1f} с: {} ({})".format(
            timeout,
            selector.name or selector.automation_id or selector.control_type,
            last_error or "нет кандидатов",
        )
    )
