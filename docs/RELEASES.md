# Версионирование и релизы

## Source of truth

Файл `VERSION` — единственный источник версии release. Формат — Semantic Versioning:

```text
MAJOR.MINOR.PATCH
```

Допускаются prerelease-версии, например `0.3.0-beta.1`.

## Подготовка версии

```powershell
.\scripts\set-version.ps1 0.2.1
```

Затем:
1. обновить `CHANGELOG.md`;
2. выполнить тесты;
3. commit;
4. push в `main`.

Изменение `VERSION` в `main` запускает `.github/workflows/release.yml`.

## Что делает release workflow

1. валидирует SemVer;
2. запрещает переиспользование существующего tag/release;
3. устанавливает зафиксированные Python dependencies;
4. запускает pytest;
5. собирает PyInstaller `onedir`;
6. запускает smoke-test именно собранного EXE;
7. компилирует Inno Setup installer;
8. собирает offline developer bundle;
9. рассчитывает SHA-256 для всех пользовательских assets;
10. создает GitHub artifact attestation;
11. создает `v<version>` tag и GitHub Release;
12. добавляет автоматически сгенерированные release notes.

## Release assets

```text
WinAutomator-<version>-Setup-win-x64.exe
WinAutomator-<version>-win-x64.zip
WinAutomator-<version>-offline-dev.zip
SHA256SUMS.txt
```

`Setup.exe` и portable ZIP предназначены для оператора и уже содержат runtime — Python отдельно не нужен.

`offline-dev.zip` предназначен для разработки/диагностики в air-gapped сети и содержит installer Python 3.8.10 + wheels.

## Почему release нельзя перезаписать

Workflow отказывается публиковать уже существующий `v<version>`. Если бинарник изменился, должна измениться и версия. Это сохраняет однозначное соответствие:

```text
version -> tag -> source commit -> build provenance -> checksums -> assets
```

## Выбор номера

- PATCH: исправление, не меняющее контракт сценария;
- MINOR: новая совместимая функция;
- MAJOR: несовместимое изменение schema/сценариев/формата данных или принципиального поведения.

До 1.0 проект может использовать MINOR для заметных прототипных изменений.
