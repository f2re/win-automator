# Changelog

Все заметные изменения проекта фиксируются здесь. Формат близок к Keep a Changelog; версии следуют Semantic Versioning.

## [0.4.0] - 2026-08-25

### Added
- автоматическое определение строки заголовков Excel после служебных/объединённых строк;
- семантическое разрешение одинаковых значений Excel по подсказкам целевого контрола без случайного выбора;
- воспроизведение дат, ведущих нулей и десятичного разделителя в формате обучающего примера;
- SHA-256 fingerprint книги Excel для безопасного resume после остановки;
- реальный multi-window Windows UIA E2E: Excel → похожие поля → ComboBox → модальный диалог → JSON;
- тесты совместимости PowerShell-скриптов с Windows PowerShell 5.1.

### Changed
- resolver теперь учитывает process name, активное окно, класс окна, родителя и относительную геометрию;
- близкие по score элементы считаются неоднозначными и не выбираются молча;
- debug resolver trace сохранён и расширен данными control score/stable identity;
- recorder после `Tab` перепривязывается к фактически сфокусированному контролу и при завершении ввода считывает реальное значение UIA;
- executor проверяет, что поле действительно приняло значение;
- физический `click_input` используется до InvokePattern, чтобы модальный `ShowDialog` не блокировал следующий шаг;
- новый hardening полностью интегрирован с debug-capture и FULL-OFFLINE release pipeline версии 0.3.1.

### Fixed
- исключена запись следующего текста в предыдущий контрол после перехода по Tab;
- исправлена потеря формата typed Excel values (`01.02.2020`, `0007`, десятичная запятая);
- исправлен resume по изменённой книге с тем же путём;
- control type сам по себе больше не считается достаточным идентификатором элемента;
- исправлено зависание цепочки шагов при кнопке, открывающей модальный WinForms-диалог.

## [0.3.1] - 2026-08-25

### Fixed
- операторский offline-путь больше не смешивается с developer bootstrap: для изолированной машины создаётся отдельный полностью готовый `FULL-OFFLINE` пакет;
- доказательство air-gap больше не основано только на `HTTP_PROXY`: installer и оба application EXE дополнительно получают Windows Firewall outbound `BLOCK` во время проверки;
- финальный portable/installed запуск теперь проверяется с реально заблокированным исходящим сетевым доступом;
- системный Python и сторонние инструменты исключаются из `PATH` во время строгого target-test;
- GitHub Release больше не публикуется до успешной проверки точного FULL-OFFLINE release candidate.

### Added
- `WinAutomator-<version>-FULL-OFFLINE-win-x64.zip` с готовым Setup и готовым portable runtime;
- `INSTALL.cmd` и `RUN-PORTABLE.cmd` как простые точки входа для машины без Интернета;
- `OFFLINE-MANIFEST.json` с размером и SHA-256 каждого внутреннего payload-файла;
- `VERIFY-OFFLINE.ps1` для локальной проверки целостности и packaged smoke-test перед запуском;
- `scripts/verify-airgap-release.ps1` для строгого install/launch/uninstall теста на чистом Windows runner;
- `AIRGAP-VERIFICATION.json` как машинно-читаемое доказательство каждого опубликованного release;
- release pipeline `build -> airgap-verify -> publish`.

## [0.3.0] - 2026-08-25

### Added
- отдельный режим **«Win Automator — сбор отладки»** (`--debug-capture`) для воспроизведения пользовательских проблем;
- глобальный таймлайн кликов, смены активных окон, навигационных клавиш и интервалов текстового ввода;
- F10-метка проблемы с UIA + Win32 snapshot активного окна; F11 завершает сессию и создаёт ZIP;
- опциональные BMP-снимки активного окна;
- автоматический запуск обычного Win Automator внутри диагностической сессии;
- межпроцессный JSONL debug sink без отдельного сервера/IPC;
- внутренние события Recorder: inspection, auto-mapping, semantic steps, pause/stop;
- внутренние события Executor: начало/успех/ошибка шага, используемый fallback и длительность;
- resolver diagnostics: лучший кандидат, selector score, минимальный score и число просмотренных кандидатов;
- Excel schema trace без строк данных;
- `SUMMARY.md`, `metadata.json`, context snapshots и SHA-256 `manifest.json` внутри debug ZIP;
- отдельный ярлык режима сбора отладки в меню «Пуск»;
- документация `docs/DEBUG.md`;
- unit-тесты redaction/export и проверка debug trace внутри реального UIA E2E.

### Privacy
- значения полей, строки Excel и скриншоты не сохраняются по умолчанию;
- текстовый ввод по умолчанию фиксируется только как длина;
- имена `Edit`, `Document` и `ListItem`, которые могут содержать введённые данные, маскируются;
- имя пользователя Windows и имя компьютера не записываются;
- сохранение значений и скриншотов включается оператором отдельно.

## [0.2.1] - 2026-08-24

### Fixed
- `bootstrap.ps1 -Offline` больше не пытается скачать `pip`, `setuptools` или `wheel` из Интернета;
- offline bundle теперь включает bootstrap wheels и SHA-256 каждого payload-файла;
- Python 3.8.10 installer проверяется по SHA-256 и издателю Python Software Foundation;
- некорректный/неполный приватный Python runtime автоматически переустанавливается вместо молчаливого использования.

### Added
- реальный UI Automation E2E на WinForms через штатный `Executor`: Unicode `SET_VALUE`, ComboBox `SELECT`, Button `CLICK`;
- полный packaged-runtime smoke-test для `tkinter/Tcl`, `openpyxl`, `pywinauto`, `pywin32`, `comtypes`, `pynput`, SQLite, scenario JSON и `%LOCALAPPDATA%`;
- отдельный GUI smoke-test уже упакованного и установленного EXE;
- CI с отдельным чистым Windows runner для air-gapped bootstrap/build при намеренно недоступной сети;
- проверка обычного запуска GUI после установки Inno Setup и после распаковки portable ZIP;
- `build.ps1 -Offline` для воспроизводимой сборки из заранее подготовленного offline bundle.

## [0.2.0] - 2026-08-24

### Added
- единый `VERSION` как источник SemVer;
- автоматический GitHub Release при изменении `VERSION` в `main`;
- Inno Setup installer для установки без прав администратора;
- portable ZIP и air-gapped developer bundle;
- SHA-256 manifest для release assets;
- GitHub build provenance attestation;
- smoke-test уже собранного `WinAutomator.exe`;
- документация по установке, архитектуре, примерам и релизам;
- issue templates, pull request template, CODEOWNERS и Dependabot;
- готовый пример `employee-entry` с Excel и scenario JSON.

### Changed
- CI теперь проверяет release manifest и автономную сборку;
- версия приложения читается из `VERSION` и попадает в `version.json`;
- offline dependency preparation проверяет Authenticode-подпись Python installer.

## [0.1.0] - 2026-08-24

### Added
- первый обучаемый Windows automation prototype;
- Excel source, recorder, UIA/Win32 inspector, scenario model, executor and SQLite checkpoint;
- базовый Windows GitHub Actions build.
