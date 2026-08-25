from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sys
import threading
import time
import traceback
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from .models import Scenario, Selector, Step
from .storage import data_dir

ENV_DEBUG_DIR = "WIN_AUTOMATOR_DEBUG_DIR"
ENV_DEBUG_VALUES = "WIN_AUTOMATOR_DEBUG_VALUES"
ACTIVE_MARKER = ".active"


def _utc_iso(ts: Optional[float] = None) -> str:
    return datetime.fromtimestamp(ts or time.time(), timezone.utc).isoformat()


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]


def _limit_text(value: Any, limit: int = 300) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


@dataclass
class DebugOptions:
    include_values: bool = False
    include_screenshots: bool = False
    max_tree_nodes: int = 400


class DebugSink:
    """Lightweight append-only event writer used by the normal application.

    Each process writes to its own JSONL file, so a diagnostic controller can
    collect raw input while the launched Win Automator process writes semantic
    recorder/executor events into the same session directory without IPC.
    """

    def __init__(
        self,
        root: Path,
        source: str = "app",
        include_values: bool = False,
    ) -> None:
        self.root = Path(root)
        self.source = source
        self.include_values = bool(include_values)
        self.root.mkdir(parents=True, exist_ok=True)
        safe_source = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in source)
        self.events_path = self.root / "events-{}-{}.jsonl".format(safe_source, os.getpid())
        self._lock = threading.RLock()
        self._seq = 0

    @classmethod
    def from_environment(cls, source: str = "app") -> Optional["DebugSink"]:
        raw = os.environ.get(ENV_DEBUG_DIR, "").strip()
        if not raw:
            return None
        root = Path(raw)
        if not (root / ACTIVE_MARKER).exists():
            return None
        include_values = os.environ.get(ENV_DEBUG_VALUES, "0") == "1"
        return cls(root, source=source, include_values=include_values)

    @property
    def active(self) -> bool:
        return (self.root / ACTIVE_MARKER).exists()

    def _redact_selector(self, selector: Optional[Selector]) -> Optional[Dict[str, Any]]:
        if selector is None:
            return None
        data = asdict(selector)
        control_type = str(data.get("control_type") or "").casefold().replace(" ", "")
        if not self.include_values and control_type in {"edit", "document", "listitem"}:
            name = str(data.get("name") or "")
            if name:
                data["name_hash"] = _short_hash(name)
                data["name_length"] = len(name)
                data["name"] = "<redacted>"
        return data

    def _redact_step(self, step: Step) -> Dict[str, Any]:
        data = step.to_dict()
        if step.target:
            data["target"] = self._redact_selector(step.target)
        value = data.get("value")
        if isinstance(value, dict) and not self.include_values:
            if value.get("literal") not in (None, ""):
                literal = str(value.get("literal"))
                value["literal_hash"] = _short_hash(literal)
                value["literal_length"] = len(literal)
                value["literal"] = "<redacted>"
        return data

    def sanitize_scenario(self, scenario: Scenario) -> Dict[str, Any]:
        result = {
            "version": scenario.version,
            "name": scenario.name,
            "steps": [self._redact_step(step) for step in scenario.steps],
        }
        if self.include_values:
            result["mappings"] = scenario.mappings
        else:
            result["mappings"] = {
                column: {"entries": len(mapping)} for column, mapping in scenario.mappings.items()
            }
        return result

    def log(self, event_type: str, **data: Any) -> None:
        if not self.active:
            return
        with self._lock:
            self._seq += 1
            event = {
                "ts": time.time(),
                "utc": _utc_iso(),
                "pid": os.getpid(),
                "source": self.source,
                "seq": self._seq,
                "type": event_type,
                "data": _json_safe(data),
            }
            with self.events_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")

    def record_semantic_step(self, step: Step, origin: str = "recorder") -> None:
        self.log("semantic_step", origin=origin, step=self._redact_step(step))

    def record_executor_step(
        self,
        stage: str,
        index: int,
        step: Step,
        method: str = "",
        duration_ms: Optional[int] = None,
        error: str = "",
    ) -> None:
        payload: Dict[str, Any] = {
            "stage": stage,
            "index": index,
            "step": self._redact_step(step),
        }
        if method:
            payload["method"] = method
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        if error:
            payload["error"] = _limit_text(error, 1000)
        self.log("executor_step", **payload)

    def record_resolver(self, index: int, diagnostic: Dict[str, Any]) -> None:
        payload = dict(diagnostic)
        candidate = payload.get("candidate")
        if isinstance(candidate, dict) and not self.include_values:
            ctype = str(candidate.get("control_type") or "").casefold().replace(" ", "")
            if ctype in {"edit", "document", "listitem"} and candidate.get("name"):
                name = str(candidate["name"])
                candidate["name_hash"] = _short_hash(name)
                candidate["name_length"] = len(name)
                candidate["name"] = "<redacted>"
        self.log("resolver", index=index, diagnostic=payload)

    def record_excel_schema(self, path: Path, sheet: str, headers: Iterable[str], rows: int) -> None:
        self.log(
            "excel_schema",
            file_name=Path(path).name,
            sheet=sheet,
            headers=list(headers),
            row_count=int(rows),
        )


@dataclass
class _RawInputState:
    text_count: int = 0
    text_value: str = ""
    target: Optional[Selector] = None


class DebugSession(DebugSink):
    """Controller-side diagnostic session with raw input and UI snapshots."""

    def __init__(
        self,
        options: Optional[DebugOptions] = None,
        on_finish_hotkey: Optional[Callable[[], None]] = None,
    ) -> None:
        self.options = options or DebugOptions()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        session_id = "{}-{}".format(stamp, uuid.uuid4().hex[:8])
        root = data_dir() / "debug" / "raw" / session_id
        root.mkdir(parents=True, exist_ok=True)
        super().__init__(root, source="controller", include_values=self.options.include_values)
        self.session_id = session_id
        self.packages_dir = data_dir() / "debug" / "packages"
        self.packages_dir.mkdir(parents=True, exist_ok=True)
        self.on_finish_hotkey = on_finish_hotkey
        self._running = False
        self._mouse_listener = None
        self._keyboard_listener = None
        self._window_thread: Optional[threading.Thread] = None
        self._raw = _RawInputState()
        self._input_lock = threading.RLock()
        self._last_window_handle = 0
        self._last_click_ts = 0.0
        self._last_click_xy = (0, 0)
        self._started_ts = time.time()

    def _metadata(self) -> Dict[str, Any]:
        width = height = None
        try:
            import ctypes

            user32 = ctypes.windll.user32
            width = int(user32.GetSystemMetrics(0))
            height = int(user32.GetSystemMetrics(1))
        except Exception:
            pass
        return {
            "format": 1,
            "session_id": self.session_id,
            "created_utc": _utc_iso(self._started_ts),
            "python": platform.python_version(),
            "python_executable_kind": "frozen" if getattr(sys, "frozen", False) else "source",
            "os": platform.platform(),
            "architecture": platform.machine(),
            "screen": {"width": width, "height": height},
            "privacy": {
                "include_values": self.options.include_values,
                "include_screenshots": self.options.include_screenshots,
                "full_excel_rows": False,
                "user_and_host_names": False,
            },
        }

    def start(self, context: Optional[Dict[str, Any]] = None) -> None:
        if self._running:
            return
        (self.root / ACTIVE_MARKER).write_text(self.session_id, encoding="utf-8")
        (self.root / "metadata.json").write_text(
            json.dumps(self._metadata(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if context:
            self._write_context("context-start.json", context)
        self._running = True
        self.log("session_start", options=asdict(self.options))
        self._start_input_listeners()
        self._window_thread = threading.Thread(target=self._window_watch_loop, daemon=True)
        self._window_thread.start()

    def _write_context(self, name: str, context: Dict[str, Any]) -> None:
        payload = dict(context)
        scenario = payload.pop("scenario", None)
        if isinstance(scenario, Scenario):
            payload["scenario"] = self.sanitize_scenario(scenario)
        elif isinstance(scenario, dict):
            payload["scenario"] = scenario
        excel_path = payload.get("excel_path")
        if excel_path:
            payload["excel_file"] = Path(str(excel_path)).name
            payload.pop("excel_path", None)
        (self.root / name).write_text(
            json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _start_input_listeners(self) -> None:
        from pynput import keyboard, mouse

        self._mouse_listener = mouse.Listener(on_click=self._on_mouse_click)
        self._keyboard_listener = keyboard.Listener(on_press=self._on_key_press)
        self._mouse_listener.start()
        self._keyboard_listener.start()

    def _on_mouse_click(self, x, y, button, pressed) -> None:
        if not self._running or not pressed:
            return
        self._flush_text_input()
        target = None
        error = ""
        try:
            from .inspector import inspect_point

            target = inspect_point(int(x), int(y))
        except Exception as exc:
            error = str(exc)
        with self._input_lock:
            self._raw.target = target
        now = time.monotonic()
        dx = int(x) - self._last_click_xy[0]
        dy = int(y) - self._last_click_xy[1]
        is_double = now - self._last_click_ts <= 0.45 and (dx * dx + dy * dy) <= 25
        self._last_click_ts = now
        self._last_click_xy = (int(x), int(y))
        self.log(
            "user_double_click" if is_double else "user_click",
            x=int(x),
            y=int(y),
            button=str(button),
            target=self._redact_selector(target),
            inspection_error=_limit_text(error, 600) if error else "",
        )

    def _on_key_press(self, key) -> None:
        if not self._running:
            return False
        from pynput.keyboard import Key

        if key == Key.f10:
            threading.Thread(target=self.mark_problem, args=("F10",), daemon=True).start()
            return
        if key == Key.f11:
            if self.on_finish_hotkey:
                self.on_finish_hotkey()
            return

        special = {
            Key.tab: "TAB",
            Key.enter: "ENTER",
            Key.esc: "ESC",
            Key.delete: "DELETE",
            Key.home: "HOME",
            Key.end: "END",
            Key.page_up: "PAGE_UP",
            Key.page_down: "PAGE_DOWN",
            Key.up: "UP",
            Key.down: "DOWN",
            Key.left: "LEFT",
            Key.right: "RIGHT",
        }
        if key in special:
            self._flush_text_input()
            self.log("user_key", key=special[key], target=self._redact_selector(self._raw.target))
            return
        if key == Key.backspace:
            with self._input_lock:
                if self._raw.text_count:
                    self._raw.text_count -= 1
                if self.include_values and self._raw.text_value:
                    self._raw.text_value = self._raw.text_value[:-1]
            return
        try:
            char = key.char
        except AttributeError:
            char = None
        if char:
            with self._input_lock:
                self._raw.text_count += 1
                if self.include_values:
                    self._raw.text_value += char

    def _flush_text_input(self) -> None:
        with self._input_lock:
            if not self._raw.text_count:
                return
            payload: Dict[str, Any] = {
                "length": self._raw.text_count,
                "target": self._redact_selector(self._raw.target),
            }
            if self.include_values:
                payload["text"] = self._raw.text_value
            self._raw.text_count = 0
            self._raw.text_value = ""
        self.log("user_text_input", **payload)

    def _window_identity(self, hwnd: int) -> Dict[str, Any]:
        import win32gui
        import win32process

        title = _limit_text(win32gui.GetWindowText(hwnd), 500)
        class_name = _limit_text(win32gui.GetClassName(hwnd), 200)
        pid = 0
        try:
            _tid, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            pass
        process_name = ""
        if pid:
            try:
                import win32api
                import win32con

                handle = win32api.OpenProcess(
                    win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid
                )
                try:
                    process_name = os.path.basename(win32process.GetModuleFileNameEx(handle, 0))
                finally:
                    handle.Close()
            except Exception:
                pass
        return {
            "hwnd": int(hwnd),
            "title": title,
            "class_name": class_name,
            "pid": int(pid or 0),
            "process_name": process_name,
        }

    def _window_watch_loop(self) -> None:
        try:
            import win32gui
        except Exception as exc:
            self.log("window_watch_error", error=str(exc))
            return
        while self._running:
            try:
                hwnd = int(win32gui.GetForegroundWindow() or 0)
                if hwnd and hwnd != self._last_window_handle:
                    self._flush_text_input()
                    self._last_window_handle = hwnd
                    self.log("foreground_window", window=self._window_identity(hwnd))
            except Exception as exc:
                self.log("window_watch_error", error=_limit_text(exc, 600))
            time.sleep(0.25)

    def _wrapper_payload(self, wrapper: Any) -> Dict[str, Any]:
        info = wrapper.element_info
        try:
            name = str(wrapper.window_text() or getattr(info, "name", "") or "")
        except Exception:
            name = str(getattr(info, "name", "") or "")
        ctype = str(getattr(info, "control_type", "") or "")
        if not self.include_values and ctype.casefold().replace(" ", "") in {"edit", "document", "listitem"}:
            original = name
            name = "<redacted>" if original else ""
            name_hash = _short_hash(original) if original else ""
        else:
            name_hash = ""
        rect = None
        try:
            r = wrapper.rectangle()
            rect = [int(r.left), int(r.top), int(r.right), int(r.bottom)]
        except Exception:
            pass
        payload = {
            "name": _limit_text(name, 300),
            "control_type": ctype,
            "automation_id": str(getattr(info, "automation_id", "") or ""),
            "class_name": str(getattr(info, "class_name", "") or ""),
            "control_id": getattr(info, "control_id", None),
            "rect": rect,
        }
        if name_hash:
            payload["name_hash"] = name_hash
        return payload

    def snapshot_active_window(self, reason: str) -> Dict[str, Any]:
        import win32gui

        hwnd = int(win32gui.GetForegroundWindow() or 0)
        if not hwnd:
            return {"error": "no foreground window"}
        stamp = datetime.now().strftime("%H%M%S-%f")[:-3]
        snapshot_dir = self.root / "snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot: Dict[str, Any] = {
            "utc": _utc_iso(),
            "reason": reason,
            "window": self._window_identity(hwnd),
            "backends": {},
        }
        try:
            from pywinauto import Desktop

            for backend in ("uia", "win32"):
                try:
                    wrapper = Desktop(backend=backend).window(handle=hwnd).wrapper_object()
                    nodes = [wrapper]
                    try:
                        nodes.extend(wrapper.descendants())
                    except Exception:
                        pass
                    limited = nodes[: max(1, int(self.options.max_tree_nodes))]
                    snapshot["backends"][backend] = {
                        "node_count_seen": len(nodes),
                        "truncated": len(nodes) > len(limited),
                        "nodes": [self._wrapper_payload(node) for node in limited],
                    }
                except Exception as exc:
                    snapshot["backends"][backend] = {"error": _limit_text(exc, 1000)}
        except Exception as exc:
            snapshot["tree_error"] = _limit_text(exc, 1000)

        json_path = snapshot_dir / "snapshot-{}.json".format(stamp)
        json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        result = {"snapshot": str(json_path.relative_to(self.root)).replace("\\", "/")}
        if self.options.include_screenshots:
            try:
                bmp_path = snapshot_dir / "window-{}.bmp".format(stamp)
                self._capture_window_bmp(hwnd, bmp_path)
                result["screenshot"] = str(bmp_path.relative_to(self.root)).replace("\\", "/")
            except Exception as exc:
                result["screenshot_error"] = _limit_text(exc, 1000)
        return result

    @staticmethod
    def _capture_window_bmp(hwnd: int, path: Path) -> None:
        import win32con
        import win32gui
        import win32ui

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = max(1, right - left)
        height = max(1, bottom - top)
        desktop = win32gui.GetDesktopWindow()
        desktop_dc = win32gui.GetWindowDC(desktop)
        source = win32ui.CreateDCFromHandle(desktop_dc)
        memory = source.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(source, width, height)
        memory.SelectObject(bitmap)
        try:
            memory.BitBlt((0, 0), (width, height), source, (left, top), win32con.SRCCOPY)
            bitmap.SaveBitmapFile(memory.GetSafeHdc(), str(path))
        finally:
            try:
                win32gui.DeleteObject(bitmap.GetHandle())
            except Exception:
                pass
            memory.DeleteDC()
            source.DeleteDC()
            win32gui.ReleaseDC(desktop, desktop_dc)

    def mark_problem(self, note: str = "") -> None:
        if not self._running:
            return
        self._flush_text_input()
        try:
            artifacts = self.snapshot_active_window(note or "problem marker")
        except Exception as exc:
            artifacts = {"snapshot_error": _limit_text(exc, 1200)}
        self.log("problem_marker", note=_limit_text(note, 2000), artifacts=artifacts)

    def record_exception(self, where: str, exc: BaseException) -> None:
        self.log(
            "exception",
            where=where,
            error=_limit_text(exc, 2000),
            traceback=_limit_text("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)), 12000),
        )
        try:
            self.mark_problem("automatic error marker: {}".format(where))
        except Exception:
            pass

    def _stop_input(self) -> None:
        self._running = False
        self._flush_text_input()
        for listener in (self._mouse_listener, self._keyboard_listener):
            try:
                if listener:
                    listener.stop()
            except Exception:
                pass
        if self._window_thread and self._window_thread.is_alive():
            self._window_thread.join(timeout=1.0)

    def _all_events(self) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for path in sorted(self.root.glob("events-*.jsonl")):
            try:
                for raw in path.read_text(encoding="utf-8").splitlines():
                    if raw.strip():
                        events.append(json.loads(raw))
            except Exception:
                continue
        events.sort(key=lambda item: (float(item.get("ts", 0.0)), int(item.get("pid", 0)), int(item.get("seq", 0))))
        return events

    def _write_summary(self, events: List[Dict[str, Any]]) -> None:
        start = events[0].get("ts", self._started_ts) if events else self._started_ts
        lines = [
            "# Win Automator debug capture",
            "",
            "Session: `{}`".format(self.session_id),
            "Started: `{}`".format(_utc_iso(float(start))),
            "Events: **{}**".format(len(events)),
            "",
            "## Timeline",
            "",
        ]
        for event in events:
            delta = max(0.0, float(event.get("ts", start)) - float(start))
            event_type = str(event.get("type", "event"))
            source = str(event.get("source", "?"))
            data = event.get("data") or {}
            detail = ""
            if event_type == "foreground_window":
                window = data.get("window") or {}
                detail = "{} · {}".format(window.get("process_name", ""), window.get("title", ""))
            elif event_type in {"user_click", "user_double_click"}:
                target = data.get("target") or {}
                detail = "{} · {}".format(target.get("control_type", ""), target.get("name", ""))
            elif event_type == "semantic_step":
                step = data.get("step") or {}
                detail = str(step.get("action", ""))
            elif event_type == "executor_step":
                detail = "{} · step {} · {}".format(data.get("stage", ""), data.get("index", ""), data.get("method", ""))
            elif event_type == "problem_marker":
                detail = "⚠ {}".format(data.get("note", ""))
            lines.append("- `+{:8.3f}s` **{}** [{}] {}".format(delta, event_type, source, _limit_text(detail, 500)))
        (self.root / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_manifest(self) -> None:
        files = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.name == "manifest.json" or path.name == ACTIVE_MARKER:
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            files.append(
                {
                    "path": str(path.relative_to(self.root)).replace("\\", "/"),
                    "size": path.stat().st_size,
                    "sha256": digest,
                }
            )
        payload = {"format": 1, "session_id": self.session_id, "files": files}
        (self.root / "manifest.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def count_events(self) -> int:
        return len(self._all_events())

    def stop(self, context: Optional[Dict[str, Any]] = None, cleanup_raw: bool = True) -> Path:
        if self._running:
            self.log("session_stop_requested")
        self._stop_input()
        if context:
            self._write_context("context-final.json", context)
        try:
            (self.root / ACTIVE_MARKER).unlink()
        except FileNotFoundError:
            pass
        time.sleep(0.15)
        events = self._all_events()
        self._write_summary(events)
        self._write_manifest()
        package = self.packages_dir / "WinAutomator-debug-{}.zip".format(self.session_id)
        with zipfile.ZipFile(str(package), "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(self.root.rglob("*")):
                if path.is_file() and path.name != ACTIVE_MARKER:
                    archive.write(str(path), arcname=str(path.relative_to(self.root)).replace("\\", "/"))
        if cleanup_raw:
            shutil.rmtree(str(self.root), ignore_errors=True)
        return package
