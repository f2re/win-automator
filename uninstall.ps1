param(
    [string]$InstallDir = '',
    [switch]$RemoveUserData
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    $local = $env:LOCALAPPDATA
    if ([string]::IsNullOrWhiteSpace($local)) { $local = Join-Path $env:USERPROFILE 'AppData\Local' }
    $InstallDir = Join-Path $local 'Programs\WinAutomator'
}

Get-Process -Name 'WinAutomator' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $InstallDir

$desktop = [Environment]::GetFolderPath('Desktop')
if (-not [string]::IsNullOrWhiteSpace($desktop)) {
    Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $desktop 'Win Automator.lnk')
}
if (-not [string]::IsNullOrWhiteSpace($env:APPDATA)) {
    Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Win Automator.lnk')
}

if ($RemoveUserData) {
    $local = $env:LOCALAPPDATA
    if ([string]::IsNullOrWhiteSpace($local)) { $local = Join-Path $env:USERPROFILE 'AppData\Local' }
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $local 'WinAutomator')
}

Write-Host 'Win Automator удалён.' -ForegroundColor Green
if (-not $RemoveUserData) {
    Write-Host 'Сценарии и checkpoint сохранены. Для их удаления запустите uninstall.ps1 -RemoveUserData.'
}
