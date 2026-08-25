# Версионирование и релизы

## Source of truth

Файл `VERSION` — единственный источник версии release. Формат — Semantic Versioning:

```text
MAJOR.MINOR.PATCH
```

Допускаются prerelease-версии, например `0.4.0-beta.1`.

## Подготовка версии

```powershell
.\scripts\set-version.ps1 0.3.1
```

Затем:

1. обновить `CHANGELOG.md`;
2. выполнить тесты;
3. commit;
4. push/merge в `main`.

Изменение `VERSION` в `main` запускает `.github/workflows/release.yml`.

## Release pipeline

Release разделён на три независимых job:

```text
build -> airgap-verify -> publish
```

### 1. `build`

Job:

- валидирует SemVer;
- запрещает переиспользование существующего tag/release;
- ставит pinned build dependencies;
- запускает unit tests и реальный UIA E2E;
- собирает PyInstaller `onedir`;
- выполняет smoke-test собранного EXE;
- компилирует Inno Setup installer;
- создаёт готовый операторский `FULL-OFFLINE` ZIP;
- отдельно создаёт developer `offline-dev.zip`;
- рассчитывает SHA-256;
- загружает весь набор как единый immutable release-candidate artifact.

### 2. `airgap-verify`

Новый чистый Windows runner скачивает **тот же release-candidate**, который позже будет опубликован.

Для `WinAutomator-<version>-FULL-OFFLINE-win-x64.zip` выполняется строгая проверка:

- manifest и SHA-256 каждого внутреннего payload;
- Windows Firewall outbound `BLOCK` для installer, portable и установленного EXE;
- dead proxy для HTTP/HTTPS/ALL_PROXY;
- удаление системного Python/сторонних инструментов из `PATH`;
- portable smoke-test;
- silent install;
- installed smoke-test;
- installed GUI smoke-test;
- installed normal GUI launch;
- portable GUI smoke-test;
- portable normal GUI launch;
- uninstall.

Результат записывается в `AIRGAP-VERIFICATION.json`.

### 3. `publish`

`publish` имеет dependency на оба предыдущих job. Если строгая air-gap проверка не прошла, GitHub Release не создаётся.

После успеха job:

- скачивает проверенный release-candidate и proof artifact;
- добавляет SHA-256 proof в `SHA256SUMS.txt`;
- создаёт GitHub artifact attestations;
- создаёт tag `v<version>`;
- публикует GitHub Release.

## Release assets

```text
WinAutomator-<version>-FULL-OFFLINE-win-x64.zip
WinAutomator-<version>-Setup-win-x64.exe
WinAutomator-<version>-win-x64.zip
WinAutomator-<version>-offline-dev.zip
AIRGAP-VERIFICATION.json
SHA256SUMS.txt
```

### `FULL-OFFLINE`

Главный пакет для целевой машины без Интернета. Содержит готовый Setup, готовый portable runtime, локальный verifier и внутренний SHA-256 manifest. Никакой Python/PyPI/bootstrap на целевой машине не выполняется.

### `Setup.exe`

Готовый операторский установщик. Runtime уже включён.

### portable ZIP

Готовый `PyInstaller onedir`. Требуется распаковывать весь каталог, а не копировать только EXE.

### `offline-dev.zip`

Developer bundle для закрытой сети. Содержит исходники, Python installer и wheels для запуска тестов/пересборки. Не является рекомендуемым операторским пакетом.

### `AIRGAP-VERIFICATION.json`

Машиночитаемое доказательство того, что точный опубликованный FULL-OFFLINE candidate был установлен и запущен с заблокированным исходящим сетевым доступом.

## Почему release нельзя перезаписать

Workflow отказывается публиковать уже существующий `v<version>`. Если бинарник изменился, должна измениться и версия. Это сохраняет однозначное соответствие:

```text
version
  -> tag
  -> source commit
  -> exact release candidate
  -> air-gap proof
  -> build provenance
  -> checksums
  -> published assets
```

## Выбор номера

- PATCH: исправление, не меняющее контракт сценария;
- MINOR: новая совместимая функция;
- MAJOR: несовместимое изменение schema/сценариев/формата данных или принципиального поведения.

До 1.0 проект может использовать MINOR для заметных прототипных изменений.
