$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $Root 'bootstrap.ps1') -NoRun
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
    Copy-Item README.md (Join-Path $Root 'dist\WinAutomator\README.md')
    $version = @{ version = '0.1.0'; python = '3.8.10'; built_at = (Get-Date).ToUniversalTime().ToString('o') } | ConvertTo-Json
    Set-Content -Path (Join-Path $Root 'dist\WinAutomator\version.json') -Value $version -Encoding UTF8
    Compress-Archive -Path (Join-Path $Root 'dist\WinAutomator\*') -DestinationPath (Join-Path $Root 'dist\WinAutomator-0.1.0-win-x64.zip') -Force
    Write-Host 'Сборка готова: dist\WinAutomator-0.1.0-win-x64.zip' -ForegroundColor Green
} finally {
    Pop-Location
}
