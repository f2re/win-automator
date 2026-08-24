# Win Automator

Обучаемый Windows-автоматизатор для переноса строк из Excel в формы настольных приложений. Оператор вручную проходит одну запись, Win Automator запоминает смысловые элементы интерфейса, связывает введённые значения со столбцами Excel и затем воспроизводит сценарий для остальных строк.

## Версия 0.1.1

В прототипе есть:

- загрузка `.xlsx` без установленного Microsoft Excel;
- выбор листа и предпросмотр данных;
- режим обучения с глобальной записью мыши и клавиатуры;
- UI Automation + Win32 fingerprint вместо жёсткой привязки к экранным координатам;
- агрегация ввода текста в смысловой `SET_VALUE`;
- автоматическая привязка введённого значения к столбцу Excel;
- ComboBox как смысловой `SELECT`;
- визуальный редактор сценария и повторный захват изменившегося элемента;
- тест сценария на одной записи и пакетная обработка;
- пауза, остановка, SQLite checkpoint и продолжение незавершённого задания;
- online bootstrap на чистой Windows;
- полностью автономный offline bootstrap из локального Python installer и wheel-кэша;
- PyInstaller `onedir`-дистрибутив, которому на целевой машине Python не нужен;
- пользовательская установка без прав администратора;
- атомарное обновление с откатом при неуспешном smoke-test;
- GitHub Actions E2E: UIA/Win32, offline-развёртывание, сборка, установка и реальный запуск EXE.

## Самый простой вариант для оператора

Скачайте готовый `WinAutomator-0.1.1-win-x64.zip`, распакуйте его и запустите двойным щелчком:

```text
install.cmd
```

Установка не требует Python и не требует прав администратора. Программа копируется в:

```text
%LOCALAPPDATA%\Programs\WinAutomator
```

Сценарии и checkpoints хранятся отдельно:

```text
%LOCALAPPDATA%\WinAutomator
```

В меню «Пуск» и на рабочем столе создаётся ярлык `Win Automator`. Перед заменой установленной версии `install.ps1` дважды проверяет встроенный `--smoke-test`: сначала в staging-каталоге, затем после атомарной установки. При ошибке старая версия восстанавливается.

Удаление:

```text
uninstall.cmd
```

По умолчанию пользовательские сценарии/checkpoints сохраняются. Для полного удаления данных можно выполнить `uninstall.ps1 -RemoveUserData`.

## Развёртывание среды разработки на Windows 10 x64

На чистой машине:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap.ps1
```

`bootstrap.ps1` автоматически:

1. скачивает официальный `python-3.8.10-amd64.exe` с `python.org`, если приватного runtime ещё нет;
2. сверяет SHA-256 `7628244cb53408b50639d2c1287c659f4e29d3dfdb9084b11aed5870c0c6a48a`;
3. проверяет Authenticode и издателя Python Software Foundation;
4. устанавливает Python только в `.runtime\python38`, не меняя системный `PATH`;
5. создаёт `.venv`;
6. устанавливает зафиксированные `pip/setuptools/wheel` и зависимости проекта;
7. выполняет self-test;
8. запускает Win Automator.

После этого можно использовать `run.bat`.

Python 3.8.10 выбран сознательно, чтобы сохранить путь к Windows 7. Для обычного пользователя release ZIP уже содержит Python runtime внутри PyInstaller-бандла.

## Полный offline bundle

На Windows-машине с Интернетом один раз выполните:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\download-offline-deps.ps1
```

Получится:

```text
offline\
├── python-3.8.10-amd64.exe
├── manifest.json
└── wheels\
    ├── pip-...
    ├── setuptools-...
    ├── wheel-...
    ├── pywinauto-...
    ├── pywin32-...
    ├── openpyxl-...
    ├── comtypes-...
    ├── pynput-...
    ├── PyInstaller-...
    ├── pytest-...
    └── транзитивные зависимости
```

`manifest.json` содержит размер и SHA-256 каждого payload-файла.

После копирования репозитория вместе с `offline` на изолированную Windows:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap.ps1 -Offline
```

В offline-режиме bootstrap не обращается к PyPI или python.org: Python installer, `pip`, `setuptools`, `wheel` и все зависимости устанавливаются только из локального bundle. Перед установкой проверяется manifest и SHA-256 каждого файла.

## Сборка готового операторского ZIP

Online:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

Из заранее подготовленного offline bundle:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -Offline
```

Результат:

```text
dist\WinAutomator-0.1.1-win-x64.zip
```

Структура ZIP:

```text
WinAutomator-0.1.1-win-x64.zip
├── WinAutomator\
│   ├── WinAutomator.exe
│   ├── python*.dll / Tcl/Tk / библиотеки PyInstaller
│   ├── README.md
│   └── version.json
├── install.cmd
├── install.ps1
├── uninstall.cmd
├── uninstall.ps1
└── README.md
```

Конечная система не скачивает и не устанавливает Python: все runtime-компоненты уже внутри каталога `WinAutomator`.

## Что проверяет CI

Workflow `Windows verified build` использует два отдельных `windows-2022` runner.

Первый runner:

1. начинает с чистого checkout;
2. запускает online `bootstrap.ps1`;
3. выполняет unit tests;
4. открывает реальную WinForms-форму и через UI Automation выполняет сценарий `SET_VALUE → SELECT → CLICK`;
5. проверяет введённый Unicode-текст и ComboBox;
6. скачивает полный набор offline-зависимостей;
7. формирует SHA-256 manifest;
8. передаёт только offline-bundle второму runner.

Второй runner:

1. получает чистый checkout и offline artifact;
2. получает намеренно нерабочие `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY`;
3. выполняет `bootstrap.ps1 -Offline -NoRun`;
4. повторяет self-test, unit tests и реальный UIA E2E;
5. выполняет `build.ps1 -Offline`;
6. запускает smoke-test уже собранного `WinAutomator.exe`;
7. распаковывает готовый distribution ZIP как на целевой системе;
8. устанавливает его в новый пользовательский каталог;
9. повторяет smoke-test после установки;
10. создаёт и уничтожает реальный GUI `Tk` (`--smoke-gui`);
11. запускает обычный `WinAutomator.exe` и проверяет, что GUI-процесс остаётся жив;
12. удаляет программу и проверяет удаление каталога;
13. только после всего этого публикует verified ZIP artifact.

Таким образом, CI проверяет не только компиляцию, но и полный путь `скачать зависимости → offline bundle → чистое offline-развёртывание → сборка → распаковка → установка → запуск`.

## Рабочий поток оператора

1. На вкладке **Данные** выберите Excel-файл.
2. Перейдите в **Сценарий** и нажмите **Обучить на первой записи**.
3. Win Automator скроется. Заполните первую строку вручную в целевой программе.
4. `F8` — пауза обучения, `F9` — завершение.
5. Проверьте получившиеся шаги.
6. При необходимости используйте **Указать заново** для control, который был найден неправильно.
7. Выполните **Проверить на второй записи**.
8. Запустите пакетную обработку.

## Формат сценария

Внутри используется простой versioned JSON, но обычный пользователь редактирует его через GUI:

```json
{
  "version": 1,
  "name": "Ввод сотрудников",
  "steps": [
    {
      "action": "set_value",
      "target": {
        "backend": "uia",
        "window_title": "Карточка сотрудника",
        "automation_id": "txtFullName",
        "control_type": "Edit",
        "name": "ФИО"
      },
      "value": {
        "source": "excel",
        "column": "ФИО",
        "literal": ""
      },
      "timeout": 10.0
    }
  ]
}
```

Control ищется по набору признаков: `AutomationId`, `ControlId`, тип, имя, класс, родитель и окно. Поэтому перемещение окна само по себе не должно ломать сценарий.

## Тестовая форма

Для ручной проверки без боевого ПО:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\TargetForm.ps1
.\.venv\Scripts\python.exe .\scripts\create_sample_data.py
```

Для автоматического E2E используется:

```powershell
.\.venv\Scripts\python.exe .\scripts\e2e_ui_test.py
```

Тест открывает WinForms, формирует selector fingerprint реальных controls, выполняет сценарий через штатный `Executor`, вводит Unicode-данные, выбирает ComboBox и нажимает Save.

## Команды MVP

- `click`
- `double_click`
- `set_value`
- `select`
- `key`
- `close_window`
- `start_app`

OCR, OpenCV, LLM, BPMN и сложный IF/ELSE намеренно не входят в MVP. Их имеет смысл добавлять только после проверки конкретных боевых приложений, где UIA/Win32 действительно недостаточно.

## Ограничения

- Во время автоматического ввода не следует параллельно управлять той же целевой программой мышью/клавиатурой.
- Полностью custom-drawn controls могут быть невидимы для UIA/Win32; для них понадобится отдельный fallback.
- Python 3.8 уже EOL и используется только как изолированный совместимый runtime. Версии библиотек зафиксированы, а операторская поставка не требует системного Python.

## Архитектура

```text
Excel (.xlsx)
     │
     ▼
 ExcelSource
     │
     ├── обучающая строка ─────────┐
     │                             │
     ▼                             ▼
SemanticRecorder ──► Inspector/UIA/Win32
     │
     ▼
Scenario JSON
     │
     ├──► Editor / re-pick
     │
     ▼
Executor ──► selector scoring ──► Windows application
     │
     ▼
Checkpoint SQLite ──► resume / retry
```
