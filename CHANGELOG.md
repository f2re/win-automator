# Changelog

Все заметные изменения проекта фиксируются здесь. Формат близок к Keep a Changelog; версии следуют Semantic Versioning.

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
