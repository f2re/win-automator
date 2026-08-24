from __future__ import annotations

import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from .excel_source import ExcelSource
from .executor import Executor
from .inspector import inspect_cursor
from .models import Scenario, Step, ValueSpec
from .recorder import SemanticRecorder
from .storage import CheckpointDB, data_dir, excel_fingerprint


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Win Automator")
        self.geometry("1020x720")
        self.minsize(860, 600)
        self.option_add("*Font", ("Segoe UI", 10))

        self.excel: Optional[ExcelSource] = None
        self.excel_path = tk.StringVar()
        self.sheet = tk.StringVar()
        self.headers: List[str] = []
        self.rows: List[Dict[str, object]] = []
        self.header_row = 1
        self.scenario = Scenario(name="Новый сценарий")
        self.recorder: Optional[SemanticRecorder] = None
        self.db = CheckpointDB()
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.current_job_id: Optional[int] = None
        self.current_row = 0

        self._build_ui()
        self._refresh_steps()

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self, padding=(16, 14))
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Win Automator", font=("Segoe UI Semibold", 18)).pack(side="left")
        ttk.Label(toolbar, text="Excel → обучение → выполнение", foreground="#666").pack(side="left", padx=14)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self.data_tab = ttk.Frame(notebook, padding=14)
        self.scenario_tab = ttk.Frame(notebook, padding=14)
        self.run_tab = ttk.Frame(notebook, padding=14)
        notebook.add(self.data_tab, text="1. Данные")
        notebook.add(self.scenario_tab, text="2. Сценарий")
        notebook.add(self.run_tab, text="3. Выполнение")

        self._build_data_tab()
        self._build_scenario_tab()
        self._build_run_tab()

        self.status = tk.StringVar(value="Готово")
        ttk.Label(self, textvariable=self.status, anchor="w", padding=(16, 4)).pack(fill="x", side="bottom")

    def _build_data_tab(self) -> None:
        top = ttk.Frame(self.data_tab)
        top.pack(fill="x")
        ttk.Label(top, text="Excel-файл").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.excel_path, state="readonly", width=72).grid(row=1, column=0, sticky="ew", pady=(4, 10))
        ttk.Button(top, text="Выбрать…", command=self.choose_excel).grid(row=1, column=1, padx=(8, 0), pady=(4, 10))
        ttk.Label(top, text="Лист").grid(row=2, column=0, sticky="w")
        self.sheet_combo = ttk.Combobox(top, textvariable=self.sheet, state="readonly", width=40)
        self.sheet_combo.grid(row=3, column=0, sticky="w", pady=(4, 12))
        self.sheet_combo.bind("<<ComboboxSelected>>", lambda _e: self.load_sheet())
        top.columnconfigure(0, weight=1)

        ttk.Label(self.data_tab, text="Предпросмотр").pack(anchor="w", pady=(4, 4))
        frame = ttk.Frame(self.data_tab)
        frame.pack(fill="both", expand=True)
        self.preview = ttk.Treeview(frame, show="headings", height=14)
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=self.preview.yview)
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=self.preview.xview)
        self.preview.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.preview.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

    def _build_scenario_tab(self) -> None:
        controls = ttk.Frame(self.scenario_tab)
        controls.pack(fill="x", pady=(0, 10))
        ttk.Button(controls, text="● Обучить на первой записи", command=self.start_recording).pack(side="left")
        ttk.Button(controls, text="Загрузить сценарий", command=self.load_scenario).pack(side="left", padx=6)
        ttk.Button(controls, text="Сохранить", command=self.save_scenario).pack(side="left")
        ttk.Button(controls, text="+ Шаг", command=self.add_step).pack(side="right")

        frame = ttk.Frame(self.scenario_tab)
        frame.pack(fill="both", expand=True)
        self.steps = ttk.Treeview(frame, columns=("n", "action", "target", "value"), show="headings")
        for key, title, width in (
            ("n", "№", 45),
            ("action", "Действие", 130),
            ("target", "Элемент", 300),
            ("value", "Значение", 320),
        ):
            self.steps.heading(key, text=title)
            self.steps.column(key, width=width, anchor="w")
        self.steps.pack(fill="both", expand=True)
        self.steps.bind("<Double-1>", lambda _e: self.edit_selected_step())

        bottom = ttk.Frame(self.scenario_tab)
        bottom.pack(fill="x", pady=(10, 0))
        ttk.Button(bottom, text="Редактировать", command=self.edit_selected_step).pack(side="left")
        ttk.Button(bottom, text="Удалить", command=self.delete_selected_step).pack(side="left", padx=6)
        ttk.Button(bottom, text="↑", width=4, command=lambda: self.move_step(-1)).pack(side="left")
        ttk.Button(bottom, text="↓", width=4, command=lambda: self.move_step(1)).pack(side="left", padx=4)
        ttk.Button(bottom, text="Проверить на второй записи", command=self.test_scenario).pack(side="right")

    def _build_run_tab(self) -> None:
        ttk.Label(self.run_tab, text="Автоматическая обработка", font=("Segoe UI Semibold", 16)).pack(anchor="w")
        self.run_summary = tk.StringVar(value="Загрузите Excel и подготовьте сценарий.")
        ttk.Label(self.run_tab, textvariable=self.run_summary).pack(anchor="w", pady=(8, 20))
        self.progress = ttk.Progressbar(self.run_tab, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x")
        self.run_state = tk.StringVar(value="")
        ttk.Label(self.run_tab, textvariable=self.run_state, font=("Segoe UI", 11)).pack(anchor="w", pady=16)
        buttons = ttk.Frame(self.run_tab)
        buttons.pack(fill="x")
        self.run_button = ttk.Button(buttons, text="▶ Запустить", command=self.start_batch)
        self.run_button.pack(side="left")
        self.pause_button = ttk.Button(buttons, text="Пауза", command=self.toggle_pause, state="disabled")
        self.pause_button.pack(side="left", padx=6)
        self.stop_button = ttk.Button(buttons, text="Остановить", command=self.stop_batch, state="disabled")
        self.stop_button.pack(side="left")

    def choose_excel(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx"), ("Все файлы", "*.*")])
        if not path:
            return
        try:
            if self.excel:
                self.excel.close()
            self.excel = ExcelSource(Path(path))
            self.excel_path.set(path)
            self.current_job_id = None
            self.sheet_combo["values"] = self.excel.sheets
            if self.excel.sheets:
                self.sheet.set(self.excel.sheets[0])
                self.load_sheet()
        except Exception as exc:
            messagebox.showerror("Excel", str(exc))

    def load_sheet(self) -> None:
        if not self.excel or not self.sheet.get():
            return
        self.current_job_id = None
        self.header_row = self.excel.detect_header_row(self.sheet.get())
        self.headers, self.rows = self.excel.read(self.sheet.get(), header_row=self.header_row)
        self.preview.delete(*self.preview.get_children())
        self.preview["columns"] = self.headers
        for header in self.headers:
            self.preview.heading(header, text=header)
            self.preview.column(header, width=150, anchor="w")
        for row in self.rows[:50]:
            self.preview.insert("", "end", values=[row.get(h, "") for h in self.headers])
        self.run_summary.set(
            "{} записей, {} столбцов · заголовки: строка {}".format(
                len(self.rows), len(self.headers), self.header_row
            )
        )
        self.status.set("Загружено {} записей".format(len(self.rows)))

    def start_recording(self) -> None:
        if not self.rows:
            messagebox.showwarning("Обучение", "Сначала выберите Excel-файл с данными.")
            return
        if self.recorder and self.recorder.running:
            return
        if not messagebox.askokcancel(
            "Обучение",
            "Сейчас окно Win Automator будет скрыто. Введите первую запись вручную в целевой программе.\n\nF8 — пауза\nF9 — завершить обучение.",
        ):
            return

        def stopped():
            self.after(0, self._finish_recording)

        self.scenario = Scenario(name="Сценарий из {}".format(Path(self.excel_path.get()).stem))
        self.recorder = SemanticRecorder(self.rows[0], on_stop=stopped)
        self.recorder.start()
        self.status.set("● Идёт обучение. F9 — завершить")
        self.withdraw()

    def _finish_recording(self) -> None:
        self.deiconify()
        self.lift()
        if self.recorder:
            self.scenario.steps = list(self.recorder.steps)
        self._refresh_steps()
        self.status.set("Обучение завершено: {} действий".format(len(self.scenario.steps)))
        self.save_scenario(silent=True)

    def _step_values(self, step: Step):
        target = ""
        if step.target:
            target = step.target.name or step.target.automation_id or step.target.control_type
        value = ""
        if step.value:
            value = "[{}]".format(step.value.column) if step.value.source == "excel" else str(step.value.literal)
        elif step.key:
            value = step.key
        return target, value

    def _refresh_steps(self) -> None:
        if not hasattr(self, "steps"):
            return
        self.steps.delete(*self.steps.get_children())
        labels = {
            "click": "Нажать",
            "double_click": "Двойной щелчок",
            "set_value": "Заполнить",
            "select": "Выбрать",
            "key": "Клавиша",
            "close_window": "Закрыть окно",
            "start_app": "Запустить",
        }
        for index, step in enumerate(self.scenario.steps):
            target, value = self._step_values(step)
            self.steps.insert("", "end", iid=str(index), values=(index + 1, labels.get(step.action, step.action), target, value))

    def _selected_index(self) -> Optional[int]:
        selection = self.steps.selection()
        if not selection:
            return None
        return int(selection[0])

    def add_step(self) -> None:
        step = Step(action="click", description="Новый шаг")
        self.scenario.steps.append(step)
        self._refresh_steps()
        self.steps.selection_set(str(len(self.scenario.steps) - 1))
        self.edit_selected_step()

    def delete_selected_step(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        del self.scenario.steps[index]
        self._refresh_steps()

    def move_step(self, delta: int) -> None:
        index = self._selected_index()
        if index is None:
            return
        new_index = index + delta
        if not (0 <= new_index < len(self.scenario.steps)):
            return
        self.scenario.steps[index], self.scenario.steps[new_index] = self.scenario.steps[new_index], self.scenario.steps[index]
        self._refresh_steps()
        self.steps.selection_set(str(new_index))

    def edit_selected_step(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        StepEditor(self, self.scenario.steps[index], self.headers, on_save=self._refresh_steps)

    def save_scenario(self, silent: bool = False) -> None:
        if not self.scenario.steps:
            if not silent:
                messagebox.showwarning("Сценарий", "Сценарий пока пуст.")
            return
        default = data_dir() / "scenarios" / "{}.json".format(self.scenario.name.replace(" ", "_"))
        if silent:
            path = default
        else:
            path_str = filedialog.asksaveasfilename(
                defaultextension=".json",
                initialfile=default.name,
                filetypes=[("Сценарий Win Automator", "*.json")],
            )
            if not path_str:
                return
            path = Path(path_str)
        self.scenario.save(path)
        self.status.set("Сценарий сохранён: {}".format(path.name))

    def load_scenario(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Сценарий Win Automator", "*.json")])
        if not path:
            return
        try:
            self.scenario = Scenario.load(Path(path))
            self._refresh_steps()
            self.status.set("Сценарий загружен")
        except Exception as exc:
            messagebox.showerror("Сценарий", str(exc))

    def _run_one(self, row_index: int, done_message: str) -> None:
        if not self.rows or not self.scenario.steps:
            messagebox.showwarning("Проверка", "Нужны Excel и непустой сценарий.")
            return
        if row_index >= len(self.rows):
            messagebox.showwarning("Проверка", "Для проверки нет следующей записи.")
            return
        self.status.set("Проверяется запись {}…".format(row_index + 1))

        def worker():
            executor = Executor(on_step=lambda i, s: self.after(0, lambda: self.status.set("Шаг {}: {}".format(i + 1, s.description or s.action))))
            result = executor.run(self.scenario, self.rows[row_index])
            if result.ok:
                self.after(0, lambda: messagebox.showinfo("Проверка", done_message))
            else:
                self.after(0, lambda: messagebox.showerror("Проверка", str(result.error)))
            self.after(0, lambda: self.status.set("Готово"))

        threading.Thread(target=worker, daemon=True).start()

    def test_scenario(self) -> None:
        self._run_one(1 if len(self.rows) > 1 else 0, "Сценарий успешно выполнен на тестовой записи.")

    def start_batch(self) -> None:
        if not self.rows or not self.scenario.steps:
            messagebox.showwarning("Запуск", "Сначала загрузите Excel и подготовьте сценарий.")
            return
        self.stop_event.clear()
        self.pause_event.set()
        start_index = 0
        try:
            fingerprint = excel_fingerprint(Path(self.excel_path.get()))
        except Exception as exc:
            messagebox.showerror("Запуск", "Не удалось проверить Excel-файл: {}".format(exc))
            return

        incomplete = self.db.latest_incomplete(
            self.excel_path.get(), self.sheet.get(), self.scenario.name, fingerprint=fingerprint
        )
        resume_existing = False
        if incomplete and incomplete[1] < len(self.rows):
            if messagebox.askyesno("Продолжить", "Есть незавершённое задание. Продолжить с записи {}?".format(incomplete[1] + 1)):
                start_index = int(incomplete[1])
                self.current_job_id = int(incomplete[0])
                resume_existing = True
        if not resume_existing:
            self.current_job_id = self.db.create_job(
                self.excel_path.get(),
                self.sheet.get(),
                self.scenario.name,
                len(self.rows),
                fingerprint=fingerprint,
            )
        self.progress["maximum"] = len(self.rows)
        self.progress["value"] = start_index
        self.run_button.configure(state="disabled")
        self.pause_button.configure(state="normal")
        self.stop_button.configure(state="normal")
        threading.Thread(target=self._batch_worker, args=(start_index,), daemon=True).start()

    def _batch_worker(self, start_index: int) -> None:
        executor = Executor()
        for index in range(start_index, len(self.rows)):
            if self.stop_event.is_set():
                if self.current_job_id:
                    self.db.update(self.current_job_id, index, status="stopped")
                break
            self.pause_event.wait()
            self.current_row = index
            self.after(0, lambda i=index: self._set_run_progress(i, "Запись {} из {}".format(i + 1, len(self.rows))))
            result = executor.run(self.scenario, self.rows[index])
            if not result.ok:
                if self.current_job_id:
                    self.db.update(self.current_job_id, index, status="error", error=str(result.error))
                self.after(0, lambda err=str(result.error): self._batch_error(err))
                return
            if self.current_job_id:
                self.db.update(self.current_job_id, index + 1)
            self.after(0, lambda i=index: self._set_run_progress(i + 1, "Выполнено {} из {}".format(i + 1, len(self.rows))))
        else:
            if self.current_job_id:
                self.db.update(self.current_job_id, len(self.rows), status="done")
            self.after(0, self._batch_done)
            return
        self.after(0, self._batch_stopped)

    def _set_run_progress(self, value: int, text: str) -> None:
        self.progress["value"] = value
        self.run_state.set(text)

    def _batch_error(self, error: str) -> None:
        self._batch_stopped()
        messagebox.showerror(
            "Автоматизация остановлена",
            error + "\n\nИсправьте шаг в редакторе или укажите элемент заново, затем снова нажмите «Запустить»: будет предложено продолжить с проблемной записи.",
        )

    def _batch_done(self) -> None:
        self._batch_stopped()
        self.progress["value"] = len(self.rows)
        self.run_state.set("Готово: обработано {} записей".format(len(self.rows)))
        messagebox.showinfo("Готово", "Обработка завершена.")

    def _batch_stopped(self) -> None:
        self.run_button.configure(state="normal")
        self.pause_button.configure(state="disabled", text="Пауза")
        self.stop_button.configure(state="disabled")
        self.pause_event.set()

    def toggle_pause(self) -> None:
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_button.configure(text="Продолжить")
            self.run_state.set("Пауза")
        else:
            self.pause_event.set()
            self.pause_button.configure(text="Пауза")

    def stop_batch(self) -> None:
        self.stop_event.set()
        self.pause_event.set()


class StepEditor(tk.Toplevel):
    ACTIONS = ["click", "double_click", "set_value", "select", "key", "close_window"]

    def __init__(self, parent: App, step: Step, headers: List[str], on_save) -> None:
        super().__init__(parent)
        self.parent_app = parent
        self.step = step
        self.headers = headers
        self.on_save = on_save
        self.title("Редактирование шага")
        self.geometry("560x430")
        self.transient(parent)
        self.grab_set()

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Действие").grid(row=0, column=0, sticky="w")
        self.action = tk.StringVar(value=step.action)
        ttk.Combobox(body, textvariable=self.action, values=self.ACTIONS, state="readonly").grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 12))

        ttk.Label(body, text="Элемент").grid(row=2, column=0, sticky="w")
        self.target_label = tk.StringVar(value=self._target_text())
        ttk.Entry(body, textvariable=self.target_label, state="readonly").grid(row=3, column=0, sticky="ew", pady=(4, 12))
        ttk.Button(body, text="Указать заново…", command=self.repick).grid(row=3, column=1, padx=(8, 0), pady=(4, 12))

        ttk.Label(body, text="Источник значения").grid(row=4, column=0, sticky="w")
        self.source = tk.StringVar(value=(step.value.source if step.value else "literal"))
        ttk.Radiobutton(body, text="Столбец Excel", variable=self.source, value="excel").grid(row=5, column=0, sticky="w")
        ttk.Radiobutton(body, text="Постоянное значение", variable=self.source, value="literal").grid(row=5, column=1, sticky="w")
        self.column = tk.StringVar(value=(step.value.column if step.value else ""))
        ttk.Combobox(body, textvariable=self.column, values=headers, state="readonly").grid(row=6, column=0, columnspan=2, sticky="ew", pady=(6, 8))
        self.literal = tk.StringVar(value=(str(step.value.literal) if step.value and step.value.literal is not None else ""))
        ttk.Entry(body, textvariable=self.literal).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        ttk.Label(body, text="Клавиша (для key)").grid(row=8, column=0, sticky="w")
        self.key = tk.StringVar(value=step.key)
        ttk.Entry(body, textvariable=self.key).grid(row=9, column=0, columnspan=2, sticky="ew", pady=(4, 12))

        ttk.Label(body, text="Ожидание, секунд").grid(row=10, column=0, sticky="w")
        self.timeout = tk.StringVar(value=str(step.timeout))
        ttk.Entry(body, textvariable=self.timeout, width=10).grid(row=11, column=0, sticky="w", pady=(4, 12))

        buttons = ttk.Frame(body)
        buttons.grid(row=12, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="left")
        ttk.Button(buttons, text="Сохранить", command=self.save).pack(side="left", padx=(8, 0))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

    def _target_text(self) -> str:
        target = self.step.target
        if not target:
            return "Не задан"
        return "{} · {} · {}".format(target.name or "без имени", target.control_type or "?", target.automation_id or target.class_name or "?")

    def repick(self) -> None:
        if not messagebox.askokcancel(
            "Указать элемент",
            "После нажатия OK окно скроется на 3 секунды. Наведите мышь на нужный элемент и не двигайте её.",
            parent=self,
        ):
            return
        self.parent_app.withdraw()
        self.withdraw()

        def worker():
            time.sleep(3.0)
            try:
                selector = inspect_cursor()
                self.step.target = selector
                error = None
            except Exception as exc:
                error = str(exc)
            self.parent_app.after(0, lambda: self._repick_done(error))

        threading.Thread(target=worker, daemon=True).start()

    def _repick_done(self, error: Optional[str]) -> None:
        self.parent_app.deiconify()
        self.deiconify()
        self.lift()
        if error:
            messagebox.showerror("Элемент", error, parent=self)
        self.target_label.set(self._target_text())

    def save(self) -> None:
        self.step.action = self.action.get()
        if self.step.action in ("set_value", "select", "start_app"):
            self.step.value = ValueSpec(
                source=self.source.get(),
                column=self.column.get(),
                literal=self.literal.get(),
            )
        elif self.step.action != "key":
            self.step.value = None
        self.step.key = self.key.get() if self.step.action == "key" else ""
        try:
            self.step.timeout = max(0.2, float(self.timeout.get().replace(",", ".")))
        except ValueError:
            messagebox.showerror("Шаг", "Некорректное время ожидания.", parent=self)
            return
        self.on_save()
        self.destroy()


def run() -> None:
    app = App()
    app.mainloop()
