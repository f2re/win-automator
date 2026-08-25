from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Optional

from .debug_capture import (
    ENV_DEBUG_DIR,
    ENV_DEBUG_VALUES,
    DebugOptions,
    DebugSession,
)


class DebugCaptureApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Win Automator — сбор отладки")
        self.geometry("760x620")
        self.minsize(690, 560)
        self.option_add("*Font", ("Segoe UI", 10))

        self.session: Optional[DebugSession] = None
        self.child: Optional[subprocess.Popen] = None
        self.package_path: Optional[Path] = None
        self.include_values = tk.BooleanVar(value=False)
        self.include_screenshots = tk.BooleanVar(value=False)
        self.auto_launch = tk.BooleanVar(value=True)
        self.state_text = tk.StringVar(value="Сбор не запущен")
        self.events_text = tk.StringVar(value="0 событий")
        self.package_text = tk.StringVar(value="")

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(500, self._refresh_event_count)

    def _build_ui(self) -> None:
        body = ttk.Frame(self, padding=20)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="Сбор отладки", font=("Segoe UI Semibold", 20)).pack(anchor="w")
        ttk.Label(
            body,
            text=(
                "Режим записывает последовательность действий, окна и решения движка, чтобы проблему можно было "
                "воспроизвести и исправить. Во время сбора нажмите F10 в момент неправильного поведения. "
                "F11 завершает сбор и создаёт ZIP-пакет."
            ),
            wraplength=700,
            foreground="#555",
            justify="left",
        ).pack(anchor="w", pady=(8, 18))

        note_frame = ttk.LabelFrame(body, text="Что нужно воспроизвести", padding=12)
        note_frame.pack(fill="x")
        ttk.Label(
            note_frame,
            text="Коротко опишите ожидаемое и фактическое поведение. Это попадёт в пакет отладки.",
            foreground="#666",
        ).pack(anchor="w")
        self.note = tk.Text(note_frame, height=5, wrap="word")
        self.note.pack(fill="x", pady=(8, 0))

        privacy = ttk.LabelFrame(body, text="Состав пакета", padding=12)
        privacy.pack(fill="x", pady=(14, 0))
        ttk.Checkbutton(
            privacy,
            text="Сохранять снимки активного окна (BMP; может содержать персональные данные)",
            variable=self.include_screenshots,
        ).pack(anchor="w")
        ttk.Checkbutton(
            privacy,
            text="Сохранять введённые значения из полей (по умолчанию значения маскируются)",
            variable=self.include_values,
        ).pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(
            privacy,
            text="Автоматически запустить обычный Win Automator внутри диагностической сессии",
            variable=self.auto_launch,
        ).pack(anchor="w", pady=(6, 0))
        ttk.Label(
            privacy,
            text=(
                "Всегда сохраняются: типы действий, тайминги, названия окон/контролов, UIA/Win32 fingerprint, "
                "selector score, ошибки и структура Excel без строк данных. Имя пользователя и имя компьютера не записываются."
            ),
            wraplength=690,
            foreground="#666",
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        status = ttk.LabelFrame(body, text="Состояние", padding=12)
        status.pack(fill="x", pady=(14, 0))
        row = ttk.Frame(status)
        row.pack(fill="x")
        ttk.Label(row, textvariable=self.state_text, font=("Segoe UI Semibold", 10)).pack(side="left")
        ttk.Label(row, textvariable=self.events_text, foreground="#666").pack(side="right")
        ttk.Entry(status, textvariable=self.package_text, state="readonly").pack(fill="x", pady=(8, 0))

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(16, 0))
        self.start_button = ttk.Button(buttons, text="● Начать сбор", command=self.start_capture)
        self.start_button.pack(side="left")
        self.marker_button = ttk.Button(buttons, text="F10 — отметить проблему", command=self.mark_problem, state="disabled")
        self.marker_button.pack(side="left", padx=8)
        self.finish_button = ttk.Button(buttons, text="■ Завершить и создать ZIP", command=self.finish_capture, state="disabled")
        self.finish_button.pack(side="left")
        self.open_button = ttk.Button(buttons, text="Открыть папку", command=self.open_package_folder, state="disabled")
        self.open_button.pack(side="right")

        ttk.Label(
            body,
            text=(
                "Практический порядок: Начать сбор → выполнить проблемный сценарий как обычно → F10 непосредственно "
                "до/после ошибки → при необходимости продолжить → F11. Полученный ZIP можно приложить к задаче/issue."
            ),
            wraplength=700,
            foreground="#555",
            justify="left",
        ).pack(anchor="w", pady=(18, 0))

    def _context(self) -> dict:
        return {
            "problem_description": self.note.get("1.0", "end").strip(),
            "controller_version": 1,
            "child_pid": self.child.pid if self.child and self.child.poll() is None else None,
        }

    def _normal_command(self):
        if getattr(sys, "frozen", False):
            return [sys.executable]
        repo_root = Path(__file__).resolve().parents[2]
        return [sys.executable, str(repo_root / "app.py")]

    def start_capture(self) -> None:
        if self.session is not None:
            return
        options = DebugOptions(
            include_values=self.include_values.get(),
            include_screenshots=self.include_screenshots.get(),
        )
        session = DebugSession(options=options, on_finish_hotkey=lambda: self.after(0, self.finish_capture))
        try:
            session.start(self._context())
        except Exception as exc:
            messagebox.showerror("Сбор отладки", "Не удалось запустить сбор:\n{}".format(exc), parent=self)
            return
        self.session = session
        self.package_path = None
        self.package_text.set("")
        session.log("controller_ready")

        if self.auto_launch.get():
            env = os.environ.copy()
            env[ENV_DEBUG_DIR] = str(session.root)
            env[ENV_DEBUG_VALUES] = "1" if options.include_values else "0"
            try:
                self.child = subprocess.Popen(self._normal_command(), env=env)
                session.log("child_started", pid=self.child.pid, command_kind="frozen" if getattr(sys, "frozen", False) else "source")
            except Exception as exc:
                session.log("child_start_error", error=str(exc))
                messagebox.showwarning(
                    "Сбор отладки",
                    "Сбор уже включён, но обычный Win Automator не удалось запустить автоматически:\n{}\n\n"
                    "Можно продолжить и воспроизвести проблему в уже открытом приложении. Внутренние события такого процесса не попадут в пакет.".format(exc),
                    parent=self,
                )

        self.state_text.set("● Сбор идёт · F10 — проблема · F11 — завершить")
        self.start_button.configure(state="disabled")
        self.marker_button.configure(state="normal")
        self.finish_button.configure(state="normal")
        self.include_values.set(options.include_values)
        self.include_screenshots.set(options.include_screenshots)
        self.after(800, self.iconify)

    def mark_problem(self) -> None:
        if not self.session:
            return
        session = self.session
        self.iconify()

        def worker():
            try:
                session.mark_problem("manual marker")
            except Exception as exc:
                session.log("marker_error", error=str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def finish_capture(self) -> None:
        session = self.session
        if not session:
            return
        self.deiconify()
        self.lift()
        self.state_text.set("Формируется ZIP-пакет…")
        self.marker_button.configure(state="disabled")
        self.finish_button.configure(state="disabled")
        self.update_idletasks()

        def worker():
            try:
                path = session.stop(self._context())
                error = None
            except Exception as exc:
                path = None
                error = str(exc)
            self.after(0, lambda: self._finish_done(path, error))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_done(self, path: Optional[Path], error: Optional[str]) -> None:
        self.session = None
        self.start_button.configure(state="normal")
        if error:
            self.state_text.set("Ошибка формирования пакета")
            messagebox.showerror("Сбор отладки", error, parent=self)
            return
        self.package_path = path
        self.package_text.set(str(path or ""))
        self.open_button.configure(state="normal" if path else "disabled")
        self.state_text.set("Готово: диагностический пакет сформирован")
        messagebox.showinfo(
            "Сбор отладки",
            "Диагностический ZIP готов. Его можно приложить к issue или передать разработчику.\n\n{}".format(path),
            parent=self,
        )

    def open_package_folder(self) -> None:
        if not self.package_path:
            return
        try:
            os.startfile(str(self.package_path.parent))  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror("Папка", str(exc), parent=self)

    def _refresh_event_count(self) -> None:
        try:
            if self.session:
                self.events_text.set("{} событий".format(self.session.count_events()))
        except Exception:
            pass
        self.after(700, self._refresh_event_count)

    def _on_close(self) -> None:
        if self.session:
            if not messagebox.askyesno(
                "Сбор отладки",
                "Сбор ещё идёт. Завершить его и сформировать ZIP?",
                parent=self,
            ):
                return
            self.finish_capture()
            return
        self.destroy()


def run_debug_capture() -> None:
    DebugCaptureApp().mainloop()
