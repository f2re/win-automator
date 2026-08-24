param(
    [switch]$Offline,
    [switch]$NoRun
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeRoot = Join-Path $Root '.runtime\python38'
$Downloads = Join-Path $Root '.runtime\downloads'
$Installer = Join-Path $Downloads 'python-3.8.10-amd64.exe'
$Python = Join-Path $RuntimeRoot 'python.exe'
$Venv = Join-Path $Root '.venv'
$VenvPython = Join-Path $Venv 'Scripts\python.exe'
$PythonUrl = 'https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe'
$ExpectedMd5 = '62CF1A12A5276B0259E8761D4CF4FE42'

function Write-Step([string]$Text) { Write-Host "`n==> $Text" -ForegroundColor Cyan }

if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'Этот bootstrap предназначен для Windows.' }
if (-not [Environment]::Is64BitOperatingSystem) { throw 'Прототип рассчитан на Windows x64.' }

New-Item -ItemType Directory -Force -Path $Downloads | Out-Null
New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

if (-not (Test-Path $Python)) {
    Write-Step 'Подготовка Python 3.8.10 x64'
    $OfflineInstaller = Join-Path $Root 'offline\python-3.8.10-amd64.exe'
    if ($Offline -or (Test-Path $OfflineInstaller)) {
        if (-not (Test-Path $OfflineInstaller)) { throw "Offline installer не найден: $OfflineInstaller" }
        Copy-Item $OfflineInstaller $Installer -Force
    } else {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri $PythonUrl -OutFile $Installer
    }
    $actualMd5 = (Get-FileHash -Path $Installer -Algorithm MD5).Hash.ToUpperInvariant()
    if ($actualMd5 -ne $ExpectedMd5) { throw "Контрольная сумма Python installer не совпала: $actualMd5" }
    $sig = Get-AuthenticodeSignature -FilePath $Installer
    if ($sig.Status -ne 'Valid') { throw "Некорректная цифровая подпись Python installer: $($sig.Status)" }

    $args = @(
        '/quiet',
        'InstallAllUsers=0',
        "TargetDir=`"$RuntimeRoot`"",
        'Include_launcher=0',
        'Include_test=0',
        'Include_pip=1',
        'Include_tcltk=1',
        'PrependPath=0',
        'Shortcuts=0'
    )
    $p = Start-Process -FilePath $Installer -ArgumentList $args -Wait -PassThru
    if ($p.ExitCode -ne 0 -or -not (Test-Path $Python)) { throw "Python installer завершился с кодом $($p.ExitCode)" }
}

Write-Step 'Создание виртуального окружения'
if (-not (Test-Path $VenvPython)) { & $Python -m venv $Venv }
& $VenvPython -m pip install --disable-pip-version-check 'pip==24.3.1' 'setuptools==75.3.2' 'wheel==0.45.1'

Write-Step 'Установка зависимостей'
$OfflineWheels = Join-Path $Root 'offline\wheels'
if ($Offline) {
    if (-not (Test-Path $OfflineWheels)) { throw "Offline wheels не найдены: $OfflineWheels" }
    & $VenvPython -m pip install --no-index --find-links $OfflineWheels -r (Join-Path $Root 'requirements-dev.txt')
} else {
    & $VenvPython -m pip install -r (Join-Path $Root 'requirements-dev.txt')
}

Write-Step 'Проверка среды'
& $VenvPython (Join-Path $Root 'scripts\self_test.py')
if ($LASTEXITCODE -ne 0) { throw 'Self-test не пройден.' }

if (-not $NoRun) {
    Write-Step 'Запуск Win Automator'
    & $VenvPython (Join-Path $Root 'app.py')
}
