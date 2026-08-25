# Установка и полностью автономное развертывание

## 1. Какой файл брать для компьютера без Интернета

Для целевой Windows x64 без доступа в Интернет используйте **только готовый операторский пакет**:

```text
WinAutomator-<version>-FULL-OFFLINE-win-x64.zip
```

Это не набор исходников и не кеш зависимостей. В архиве уже находятся собранное приложение, полный PyInstaller runtime и готовый Inno Setup installer.

После распаковки структура выглядит так:

```text
WinAutomator-<version>-FULL-OFFLINE\
├── INSTALL.cmd
├── RUN-PORTABLE.cmd
├── VERIFY-OFFLINE.ps1
├── OFFLINE-MANIFEST.json
├── README-OFFLINE.txt
├── setup\
│   └── WinAutomator-<version>-Setup-win-x64.exe
└── portable\
    └── WinAutomator\
        ├── WinAutomator.exe
        └── ... полный встроенный runtime и библиотеки
```

На целевой машине **не требуются**:

- Интернет;
- системный Python;
- `pip` / PyPI;
- `winget`;
- Chocolatey;
- Git;
- Microsoft Excel для чтения `.xlsx`.

## 2. Установка на полностью изолированной машине

1. Скопируйте `WinAutomator-<version>-FULL-OFFLINE-win-x64.zip` на флешку или другой разрешённый носитель.
2. Перенесите архив на целевой Windows x64 и распакуйте его целиком.
3. Запустите:

```text
INSTALL.cmd
```

Перед установкой скрипт автоматически:

1. проверяет `OFFLINE-MANIFEST.json`;
2. сверяет размер и SHA-256 **каждого** файла в пакете;
3. проверяет наличие готового Setup и portable EXE;
4. убеждается, что операторский архив не содержит `.venv`, `pip.exe`, отдельный `python.exe` или каталог developer wheels;
5. запускает packaged smoke-test portable-версии;
6. только после успешной проверки запускает вложенный Setup.

Установщик работает из локальных файлов и ничего не загружает. Программа устанавливается в профиль пользователя и не требует прав администратора.

## 3. Portable без установки

Из того же FULL-OFFLINE архива можно запустить:

```text
RUN-PORTABLE.cmd
```

Он сначала проверяет целостность архива и packaged runtime, затем запускает:

```text
portable\WinAutomator\WinAutomator.exe
```

Не переносите отдельно один `WinAutomator.exe`: PyInstaller используется в режиме `onedir`, поэтому весь каталог `portable\WinAutomator` является единым автономным приложением.

## 4. Почему release считается действительно offline

GitHub Release теперь публикуется только после отдельной проверки **точно того FULL-OFFLINE ZIP, который затем прикладывается к release**.

Проверка выполняется на новом Windows runner и включает:

1. загрузку неизменяемого release-candidate artifact;
2. распаковку `WinAutomator-<version>-FULL-OFFLINE-win-x64.zip` в пустой каталог;
3. создание Windows Firewall outbound `BLOCK` правил для вложенного installer, portable EXE и затем установленного EXE;
4. одновременную установку `HTTP_PROXY`, `HTTPS_PROXY` и `ALL_PROXY` на несуществующий `127.0.0.1:9`;
5. удаление системного Python и сторонних инструментов из `PATH` на время теста;
6. полную проверку manifest/SHA-256;
7. packaged smoke-test portable;
8. тихую установку Setup в новый каталог;
9. smoke-test установленного EXE;
10. GUI smoke-test установленного EXE;
11. обычный запуск установленного GUI;
12. smoke-test, GUI smoke-test и обычный запуск portable-копии;
13. штатное удаление приложения.

Если любой из этих этапов не проходит, job `publish` не запускается и GitHub Release не создаётся.

Иными словами, одного «плохого proxy» теперь недостаточно: сетевой доступ самого installer/application дополнительно запрещён Windows Firewall.

## 5. Доказательство для каждого release

В release публикуются:

```text
WinAutomator-<version>-FULL-OFFLINE-win-x64.zip
WinAutomator-<version>-Setup-win-x64.exe
WinAutomator-<version>-win-x64.zip
WinAutomator-<version>-offline-dev.zip
AIRGAP-VERIFICATION.json
SHA256SUMS.txt
```

`AIRGAP-VERIFICATION.json` создаётся только после успешного строгого теста и фиксирует, что:

- manifest проверен;
- установка без сети прошла;
- installed smoke/GUI/normal launch прошли;
- portable smoke/GUI/normal launch прошли;
- uninstall прошёл;
- `network_required = false`;
- `system_python_required = false`.

`SHA256SUMS.txt` содержит SHA-256 пользовательских release assets и самого файла доказательства.

## 6. Ручная проверка FULL-OFFLINE архива

После распаковки можно отдельно выполнить:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\VERIFY-OFFLINE.ps1 -Smoke
```

Успешный результат должен закончиться сообщениями:

```text
FULL-OFFLINE verification passed
Network required: NO
System Python required: NO
```

Внешний SHA-256 самого скачанного ZIP проверяется по `SHA256SUMS.txt` из того же GitHub Release:

```powershell
Get-FileHash .\WinAutomator-0.3.1-FULL-OFFLINE-win-x64.zip -Algorithm SHA256
Get-Content .\SHA256SUMS.txt
```

## 7. Обычный Setup и portable

Если FULL-OFFLINE контейнер не нужен, release также содержит:

```text
WinAutomator-<version>-Setup-win-x64.exe
WinAutomator-<version>-win-x64.zip
```

Оба уже содержат runtime приложения и не требуют системного Python. FULL-OFFLINE ZIP предпочтителен для изолированной машины, потому что вместе с бинарниками содержит локальный manifest, verifier и понятные offline-точки входа.

## 8. `offline-dev.zip` — только для разработки

```text
WinAutomator-<version>-offline-dev.zip
```

Этот архив нужен разработчику в закрытой сети, если требуется запускать исходники, тесты или пересобирать приложение. Он содержит официальный installer Python 3.8.10 x64 и заранее скачанные wheels.

Для обычного оператора этот архив **не нужен**.

Developer bootstrap:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap.ps1 -Offline
```

В `-Offline` зависимости устанавливаются только из `offline\wheels` с `--no-index`, после предварительной проверки SHA-256 manifest.

## 9. Что проверяет packaged smoke-test

Проверяется именно собранный EXE и его встроенные компоненты:

- Tcl/Tk / `tkinter`;
- `openpyxl` и локальная запись/чтение `.xlsx`;
- `pywinauto`;
- `pywin32`;
- `comtypes`;
- `pynput`;
- Windows UI Automation backend;
- SQLite checkpoint;
- scenario JSON;
- запись данных в `%LOCALAPPDATA%`;
- создание GUI в GUI smoke-test.

## 10. Совместимость

Целевая архитектура: **Windows x64**.

- Windows 10 x64 — основной целевой профиль;
- Windows 11 x64 — проверяемая современная среда;
- Windows 7 SP1 x64 остаётся минимальной заявленной целью сборки, но GitHub-hosted CI физически не предоставляет чистую Windows 7 машину, поэтому для неё требуется отдельное стендовое испытание конкретного workstation/application.

Если автоматизируемая программа запущена с повышенными правами, Windows UIPI может запретить взаимодействие процессу обычного уровня целостности. В таком случае Win Automator и целевое приложение должны работать на совместимых уровнях привилегий.
