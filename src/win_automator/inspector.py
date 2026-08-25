from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from .models import Selector


@dataclass
class Candidate:
    wrapper: object
    score: int


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


def _text(value: object) -> str:
    return str(value or "").strip().casefold()


def score_wrapper(wrapper, selector: Selector) -> int:
    info = wrapper.element_info
    score = 0
    automation_id = str(getattr(info, "automation_id", "") or "")
    control_type = str(getattr(info, "control_type", "") or "")
    class_name = str(getattr(info, "class_name", "") or "")
    control_id = getattr(info, "control_id", None)
    name = str(_safe(wrapper.window_text, "") or getattr(info, "name", "") or "")

    if selector.automation_id and automation_id == selector.automation_id:
        score += 100
    if selector.control_id is not None and control_id == selector.control_id:
        score += 90
    if selector.control_type and _text(control_type) == _text(selector.control_type):
        score += 30
    if selector.name and _text(name) == _text(selector.name):
        score += 40
    elif selector.name and (_text(selector.name) in _text(name) or _text(name) in _text(selector.name)):
        score += 15
    if selector.class_name and _text(class_name) == _text(selector.class_name):
        score += 20
    try:
        parent = wrapper.parent()
        if selector.parent_name and parent and _text(parent.window_text()) == _text(selector.parent_name):
            score += 20
    except Exception:
        pass
    return score


def _candidate_payload(wrapper, score: int) -> Dict[str, object]:
    info = wrapper.element_info
    top = wrapper.top_level_parent()
    return {
        "score": int(score),
        "name": str(_safe(wrapper.window_text, "") or getattr(info, "name", "") or ""),
        "control_type": str(getattr(info, "control_type", "") or ""),
        "automation_id": str(getattr(info, "automation_id", "") or ""),
        "class_name": str(getattr(info, "class_name", "") or ""),
        "control_id": getattr(info, "control_id", None),
        "window_title": str(_safe(top.window_text, "") or ""),
    }


def _emit(callback, payload: Dict[str, object]) -> None:
    if not callback:
        return
    try:
        callback(payload)
    except Exception:
        pass


def resolve(
    selector: Selector,
    timeout: float = 10.0,
    minimum_score: int = 30,
    diagnostic_callback: Optional[Callable[[Dict[str, object]], None]] = None,
):
    from pywinauto import Desktop

    deadline = time.time() + max(0.2, timeout)
    last_error = None
    last_best_payload: Optional[Dict[str, object]] = None
    last_signature = None
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            desktop = Desktop(backend=selector.backend or "uia")
            windows = desktop.windows()
            best: Optional[Candidate] = None
            candidate_count = 0
            for window in windows:
                try:
                    title = str(_safe(window.window_text, "") or "")
                    win_info = window.element_info
                    if selector.window_title and _text(selector.window_title) != _text(title):
                        if _text(selector.window_title) not in _text(title):
                            continue
                    if selector.window_class:
                        actual_class = str(getattr(win_info, "class_name", "") or "")
                        if actual_class and _text(actual_class) != _text(selector.window_class):
                            continue
                    candidates = [window]
                    try:
                        candidates.extend(window.descendants())
                    except Exception:
                        pass
                    for wrapper in candidates:
                        candidate_count += 1
                        current = score_wrapper(wrapper, selector)
                        if best is None or current > best.score:
                            best = Candidate(wrapper, current)
                except Exception:
                    continue
            if best:
                last_best_payload = _candidate_payload(best.wrapper, best.score)
                signature = (
                    last_best_payload.get("score"),
                    last_best_payload.get("automation_id"),
                    last_best_payload.get("control_id"),
                    last_best_payload.get("name"),
                )
                if signature != last_signature:
                    _emit(
                        diagnostic_callback,
                        {
                            "stage": "candidate",
                            "attempt": attempt,
                            "candidate_count": candidate_count,
                            "candidate": last_best_payload,
                        },
                    )
                    last_signature = signature
                if best.score >= minimum_score:
                    _emit(
                        diagnostic_callback,
                        {
                            "stage": "resolved",
                            "attempt": attempt,
                            "candidate_count": candidate_count,
                            "minimum_score": minimum_score,
                            "candidate": last_best_payload,
                        },
                    )
                    return best.wrapper
            last_error = RuntimeError("лучший score={}".format(best.score if best else 0))
        except Exception as exc:
            last_error = exc
        time.sleep(0.2)
    _emit(
        diagnostic_callback,
        {
            "stage": "timeout",
            "attempt": attempt,
            "minimum_score": minimum_score,
            "candidate": last_best_payload,
            "error": str(last_error or "нет кандидатов"),
        },
    )
    raise TimeoutError(
        "Элемент не найден за {:.1f} с: {} ({})".format(
            timeout,
            selector.name or selector.automation_id or selector.control_type,
            last_error or "нет кандидатов",
        )
    )
