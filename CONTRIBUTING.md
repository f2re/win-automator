# Contributing

## Локальная среда

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap.ps1 -NoRun
.\.venv\Scripts\python.exe -m pytest -q
```

## Перед pull request

- изменение должно иметь воспроизводимый пользовательский сценарий;
- новые behavior branches должны покрываться тестами, где это возможно;
- упаковка не должна ломать `build.ps1`;
- для изменения формата scenario необходимо описать совместимость/миграцию;
- изменение пользовательского поведения отражается в документации и `CHANGELOG.md`;
- рабочие Excel-файлы и конфиденциальные данные не коммитятся.

## Commit style

Предпочтителен Conventional Commits-подобный формат:

```text
feat: add combo-box recovery
fix: keep checkpoint after retry
docs: document offline release
build: harden Windows release pipeline
```

## Версии

Не повышайте `VERSION` в обычном feature PR без намерения выпустить релиз после merge. Изменение `VERSION` в `main` является release trigger.
