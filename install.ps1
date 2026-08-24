param(
    [string]$SourceDir = (Join-Path $PSScriptRoot 'WinAutomator'),
    [string]$InstallDir = '',
    [switch]$NoShortcut,
    [switch]$NoLaunch
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Write-Step([string]$Text) { Write-Host "`n==> $Text" -ForegroundColor Cyan }

if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'Установщик предназначен для Windows.' }
if (-not [Environment]::Is64BitOperatingSystem) { throw 'Win Automator собран для Windows x64.' }

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    $local = $env:LOCALAPPDATA
    if ([string]::IsNullOrWhiteSpace($local)) { $local = Join-Path $env:USERPROFILE 'AppData\Local' }
    $InstallDir = Join-Path $local 'Programs\WinAutomator'
}

$SourceDir = [IO.Path]::GetFullPath($SourceDir)
$InstallDir = [IO.Path]::GetFullPath($InstallDir)
$SourceExe = Join-Path $SourceDir 'WinAutomator.exe'
if (-not (Test-Path -LiteralPath $SourceExe)) { throw "В пакете не найден WinAutomator.exe: $SourceExe" }

$running = Get-Process -Name 'WinAutomator' -ErrorAction SilentlyContinue
if ($running) { throw 'Win Automator уже запущен. Закройте приложение перед установкой/обновлением.' }

$parent = Split-Path -Parent $InstallDir
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$staging = "$InstallDir.new.$PID"
$backup = "$InstallDir.old.$PID"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $staging, $backup
New-Item -ItemType Directory -Force -Path $staging | Out-Null

Write-Step 'Копирование файлов приложения'
Copy-Item -LiteralPath (Join-Path $SourceDir '*') -Destination $staging -Recurse -Force

$StagedExe = Join-Path $staging 'WinAutomator.exe'
Write-Step 'Проверка собранного приложения до установки'
$smoke = Start-Process -FilePath $StagedExe -ArgumentList '--smoke-test' -Wait -PassThru
if ($smoke.ExitCode -ne 0) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $staging
    throw "Smoke-test собранного приложения завершился с кодом $($smoke.ExitCode). Установка отменена."
}

Write-Step 'Атомарная установка'
try {
    if (Test-Path -LiteralPath $InstallDir) { Move-Item -LiteralPath $InstallDir -Destination $backup }
    Move-Item -LiteralPath $staging -Destination $InstallDir
} catch {
    if ((Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $InstallDir)) {
        Move-Item -LiteralPath $backup -Destination $InstallDir
    }
    throw
}

$InstalledExe = Join-Path $InstallDir 'WinAutomator.exe'
Write-Step 'Контрольный запуск установленной копии'
$smokeInstalled = Start-Process -FilePath $InstalledExe -ArgumentList '--smoke-test' -Wait -PassThru
if ($smokeInstalled.ExitCode -ne 0) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $InstallDir
    if (Test-Path -LiteralPath $backup) { Move-Item -LiteralPath $backup -Destination $InstallDir }
    throw "Smoke-test после установки завершился с кодом $($smokeInstalled.ExitCode). Выполнен откат."
}
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $backup

if (-not $NoShortcut) {
    Write-Step 'Создание ярлыков'
    $shell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath('Desktop')
    if (-not [string]::IsNullOrWhiteSpace($desktop)) {
        $shortcut = $shell.CreateShortcut((Join-Path $desktop 'Win Automator.lnk'))
        $shortcut.TargetPath = $InstalledExe
        $shortcut.WorkingDirectory = $InstallDir
        $shortcut.Description = 'Win Automator'
        $shortcut.Save()
    }
    if (-not [string]::IsNullOrWhiteSpace($env:APPDATA)) {
        $startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
        New-Item -ItemType Directory -Force -Path $startMenu | Out-Null
        $shortcut = $shell.CreateShortcut((Join-Path $startMenu 'Win Automator.lnk'))
        $shortcut.TargetPath = $InstalledExe
        $shortcut.WorkingDirectory = $InstallDir
        $shortcut.Description = 'Win Automator'
        $shortcut.Save()
    }
}

Write-Host "`nWin Automator установлен: $InstallDir" -ForegroundColor Green
if (-not $NoLaunch) {
    Write-Step 'Запуск Win Automator'
    Start-Process -FilePath $InstalledExe -WorkingDirectory $InstallDir | Out-Null
}
