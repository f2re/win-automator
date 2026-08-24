# Примеры

## Employee entry

Каталог `examples/employee-entry` — минимальный воспроизводимый стенд для обучения.

Состав:

```text
sample-data.xlsx
scenario.json
README.md
```

Запустите тестовую форму:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\TargetForm.ps1
```

Затем:
1. загрузите `examples\employee-entry\sample-data.xlsx`;
2. выберите лист `Employees`;
3. обучите сценарий на первой строке;
4. сравните получившийся сценарий с `scenario.json`;
5. проверьте следующую запись;
6. запустите batch.

Пример специально использует обезличенные данные. Для issue/repro рекомендуется строить такие же минимальные наборы, а не прикладывать рабочие Excel-файлы.
