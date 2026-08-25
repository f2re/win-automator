# Changelog

Все заметные изменения проекта фиксируются здесь. Формат близок к Keep a Changelog; версии следуют Semantic Versioning.

## [0.3.0] - 2026-08-25

### Added
- реальный Windows UI Automation E2E: Excel → WinForms → похожие поля → ComboBox → модальное окно → итоговый JSON;
- автоматическое определение строки заголовков Excel после служебных и объединённых строк;
- SHA-256 fingerprint исходной книги Excel для безопасного продолжения прерванного задания;
- проверки совместимости PowerShell-скриптов с Windows PowerShell 5.1.

### Changed
- resolver учитывает процесс, активное окно, класс окна, родителя и относительную геометрию элемента;
- неоднозначные UI-элементы больше не выбираются молча: выполнение останавливается с диагностикой;
- записываемый сценарий после `Tab` перепривязывается к реально сфокусированному контролу;
- при обучении сохраняется фактическое итоговое содержимое поля, включая вставку и исправления;
- даты, ведущие нули и десятичный разделитель воспроизводятся в формате обучающего примера;
- клики сначала выполняются физическим UI-вводом, что позволяет продолжать сценарий после открытия модальных диалогов;
- resume задания разрешён только для неизменившегося Excel-файла;
- PowerShell-файлы с не-ASCII текстом сохранены с UTF-8 BOM для Windows PowerShell 5.1.

### Fixed
- исключена привязка следующего ввода к предыдущему полю после перехода по `Tab`;
- устранён риск выбора первого похожего контрола только по типу;
- исправлена потеря пользовательского формата дат и числовых кодов при переносе значений из Excel;
- исправлено продолжение задания с неверной строки после замены Excel-файла по тому же пути;
- устранена блокировка сценария при `ShowDialog` после вызова кнопки через UI Automation invoke;
- устранена несовместимость кириллических PowerShell-скриптов с Windows PowerShell 5.1.

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
