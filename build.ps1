param(
    [switch]$Offline
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Version = '0.1.1'
$BootstrapArgs = @('-NoRun')
if ($Offline) { $BootstrapArgs += '-Offline' }
& (Join-Path $Root 'bootstrap.ps1') @BootstrapArgs
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap failed.' }
$Python = Join-Path $Root '.venv\Scripts\python.exe'

Push-Location $Root
try {
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }

    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist
    & $Python -m PyInstaller --noconfirm --clean --onedir --windowed `
        --name WinAutomator `
        --paths (Join-Path $Root 'src') `
        --collect-submodules comtypes `
        --hidden-import pywinauto.controls.uiawrapper `
        app.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }

    $AppDir = Join-Path $Root 'dist\WinAutomator'
    Copy-Item README.md (Join-Path $AppDir 'README.md')
    $versionInfo = @{
        version = $Version
        python = '3.8.10'
        built_at = (Get-Date).ToUniversalTime().ToString('o')
    } | ConvertTo-Json
    Set-Content -Path (Join-Path $AppDir 'version.json') -Value $versionInfo -Encoding UTF8

    Write-Host 'Проверка собранного EXE...' -ForegroundColor Cyan
    $smoke = Start-Process -FilePath (Join-Path $AppDir 'WinAutomator.exe') -ArgumentList '--smoke-test' -Wait -PassThru
    if ($smoke.ExitCode -ne 0) { throw "Built EXE smoke-test failed: $($smoke.ExitCode)" }

    $PackageRoot = Join-Path $Root 'dist\package'
    New-Item -ItemType Directory -Force -Path $PackageRoot | Out-Null
    Copy-Item -Path $AppDir -Destination (Join-Path $PackageRoot 'WinAutomator') -Recurse -Force
    Copy-Item -Path (Join-Path $Root 'install.ps1') -Destination (Join-Path $PackageRoot 'install.ps1') -Force
    Copy-Item -Path (Join-Path $Root 'uninstall.ps1') -Destination (Join-Path $PackageRoot 'uninstall.ps1') -Force
    Copy-Item -Path (Join-Path $Root 'README.md') -Destination (Join-Path $PackageRoot 'README.md') -Force

    $zip = Join-Path $Root "dist\WinAutomator-$Version-win-x64.zip"
    Compress-Archive -Path (Join-Path $PackageRoot '*') -DestinationPath $zip -Force
    Write-Host "Сборка готова: $zip" -ForegroundColor Green
} finally {
    Pop-Location
}
