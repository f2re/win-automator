# Установка и развертывание

## 1. Обычная установка

Скачайте из GitHub Releases файл:

```text
WinAutomator-<version>-Setup-win-x64.exe
```

Запустите его под обычной учетной записью. Установщик размещает приложение в:

```text
%LOCALAPPDATA%\Programs\Win Automator
```

Права администратора не требуются. После установки в меню «Пуск» появляются два ярлыка:

```text
Win Automator
Win Automator — сбор отладки
```

Второй ярлык запускает диагностический контроллер для воспроизведения проблем и создания ZIP-пакета для разработчика. Подробно: [DEBUG.md](DEBUG.md).

Python, pip и библиотеки на целевой машине не устанавливаются и не скачиваются: PyInstaller runtime уже входит в дистрибутив.

## 2. Portable

Скачайте:

```text
WinAutomator-<version>-win-x64.zip
```

Распакуйте каталог целиком и запускайте:

```text
WinAutomator\WinAutomator.exe
```

Режим сбора отладки в portable:

```powershell
.\WinAutomator\WinAutomator.exe --debug-capture
```

Не переносите только один EXE: PyInstaller использует `onedir`, поэтому рядом находятся необходимые DLL, Tcl/Tk и Python-модули. Portable-вариант также не требует системного Python.

## 3. Закрытая сеть / разработка

Release `offline-dev.zip` содержит исходный код, официальный Python 3.8.10 x64 installer и заранее скачанные wheels, включая bootstrap-компоненты `pip`, `setuptools` и `wheel`.

После распаковки:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap.ps1 -Offline
```

Bootstrap:
1. проверяет платформу x64;
2. проверяет SHA-256 Python installer и издателя Python Software Foundation;
3. проверяет `offline\manifest.json` и SHA-256 каждого payload-файла;
4. ставит приватный Python в `.runtime\python38`;
5. создает `.venv`;
6. устанавливает `pip/setuptools/wheel` только из `offline\wheels`;
7. устанавливает все зависимости проекта только из `offline\wheels` с `--no-index`;
8. выполняет self-test;
9. запускает приложение.

В режиме `-Offline` обращений к `python.org` или PyPI быть не должно.

## 4. Подготовка offline bundle

На Windows-машине с Интернетом:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\download-offline-deps.ps1
```

Будет создан каталог:

```text
offline\
├── python-3.8.10-amd64.exe
├── manifest.json
└── wheels\
    └── *.whl
```

`manifest.json` содержит размер и SHA-256 каждого installer/wheel payload. Release workflow включает этот каталог в `WinAutomator-<version>-offline-dev.zip`.

## 5. Сборка из исходников

Online:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

Полностью из заранее подготовленного offline bundle:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -Offline
```

Для создания installer должен быть установлен Inno Setup 6. Без него локальная сборка создаст portable ZIP. CI/release требует installer в основном release job и завершится ошибкой, если `ISCC.exe` недоступен.

Перед формированием ZIP `build.ps1` запускает уже собранный `WinAutomator.exe` в smoke-режиме. Проверяются Tcl/Tk, `openpyxl`, `pywinauto`, `pywin32`, `comtypes`, `pynput`, SQLite, scenario JSON, debug writer и запись пользовательских данных.

## 6. Что автоматически проверяет CI

CI использует два независимых Windows runner:

1. основной runner выполняет unit tests и реальный UI Automation E2E на WinForms; E2E дополнительно проверяет, что `Executor` пишет структурированный debug trace и при включённой маскировке не сохраняет значения полей;
2. основной runner собирает portable + Inno Setup, устанавливает Setup в новый каталог, выполняет packaged smoke/GUI smoke и проверяет обычный запуск GUI;
3. второй runner получает только подготовленный offline payload, после чего `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` направляются на несуществующий локальный proxy, а `PIP_NO_INDEX=1` запрещает индекс пакетов;
4. на втором runner с нуля выполняется `bootstrap.ps1 -Offline`, self-test, unit tests и тот же UIA E2E;
5. затем `build.ps1 -Offline` собирает portable без сети;
6. ZIP распаковывается в новый целевой каталог, выполняются packaged smoke, GUI smoke и обычный запуск приложения.

То есть CI проверяет цепочку не только до «файл собрался», а до фактического запуска поставленного приложения.

## 7. Проверка целостности релиза

Скачайте `SHA256SUMS.txt` из того же release и сравните:

```powershell
Get-FileHash .\WinAutomator-0.3.0-win-x64.zip -Algorithm SHA256
Get-FileHash .\WinAutomator-0.3.0-Setup-win-x64.exe -Algorithm SHA256
Get-Content .\SHA256SUMS.txt
```

Хэши должны полностью совпасть. Release assets также получают GitHub build provenance attestation.

## 8. Совместимость

Целевая архитектура: x64.

- Windows 7 SP1 x64 — минимальная заявленная цель;
- Windows 10 x64 — основной рабочий профиль;
- Windows 11 x64 — ожидаемая совместимость.

CI выполняется на `windows-2022`; окончательная совместимость с конкретным Windows 7/10 workstation также зависит от целевого приложения и его accessibility/UIA реализации.

Если целевое приложение запущено с повышенными правами, Windows UIPI может не позволить обычному процессу автоматизатора взаимодействовать с ним. В таком случае процессы должны работать на сопоставимом уровне целостности.
