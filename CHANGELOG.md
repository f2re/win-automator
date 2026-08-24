# Changelog

Все заметные изменения проекта фиксируются здесь. Формат близок к Keep a Changelog; версии следуют Semantic Versioning.

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
