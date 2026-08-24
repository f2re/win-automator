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

Права администратора не требуются. После установки ярлык появляется в меню «Пуск»; ярлык на рабочем столе можно выбрать в мастере.

## 2. Portable

Скачайте:

```text
WinAutomator-<version>-win-x64.zip
```

Распакуйте каталог целиком и запускайте:

```text
WinAutomator\WinAutomator.exe
```

Не переносите только один EXE: PyInstaller использует `onedir`, поэтому рядом находятся необходимые DLL и Python-модули.

## 3. Закрытая сеть / разработка

Release `offline-dev.zip` содержит исходный код, Python 3.8.10 installer и заранее скачанные wheels.

После распаковки:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap.ps1 -Offline
```

Bootstrap:
1. проверяет платформу x64;
2. проверяет контрольную сумму и Authenticode Python installer;
3. ставит приватный Python в `.runtime\python38`;
4. создает `.venv`;
5. устанавливает зависимости только из `offline\wheels`;
6. выполняет self-test;
7. запускает приложение.

## 4. Сборка из исходников

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

Для создания installer должен быть установлен Inno Setup 6. Без него локальная сборка все равно создаст portable ZIP. CI/release требует installer и завершится ошибкой, если `ISCC.exe` недоступен.

## 5. Проверка целостности

Скачайте `SHA256SUMS.txt` из того же release и сравните:

```powershell
Get-FileHash .\WinAutomator-0.2.0-win-x64.zip -Algorithm SHA256
Get-Content .\SHA256SUMS.txt
```

Хэш должен полностью совпасть.

## 6. Совместимость

Целевая архитектура: x64.

- Windows 7 SP1 x64 — минимальная заявленная цель;
- Windows 10 x64 — основной рабочий профиль;
- Windows 11 x64 — ожидаемая совместимость.

Если целевое приложение запущено с повышенными правами, Windows UIPI может не позволить обычному процессу автоматизатора взаимодействовать с ним. В таком случае процессы должны работать на сопоставимом уровне целостности.
