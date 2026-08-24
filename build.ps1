param(
    [switch]$Offline
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Version = '0.1.1'

function Invoke-SmokeWithTimeout {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [string]$Argument = '--smoke-test',
        [int]$TimeoutSeconds = 30
    )
    $process = Start-Process -FilePath $FilePath -ArgumentList $Argument -PassThru
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        try { $process.Kill() } catch {}
        try { $process.WaitForExit() } catch {}
        throw "Smoke-test timed out after $TimeoutSeconds seconds: $FilePath $Argument"
    }
    if ($process.ExitCode -ne 0) {
        throw "Smoke-test failed with exit code $($process.ExitCode): $FilePath $Argument"
    }
}

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
    Write-Host 'Building WinAutomator.exe with PyInstaller...' -ForegroundColor Cyan
    & $Python -m PyInstaller --noconfirm --clean --onedir --windowed `
        --name WinAutomator `
        --paths (Join-Path $Root 'src') `
        --collect-submodules comtypes `
        --hidden-import pywinauto.controls.uiawrapper `
        app.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
    Write-Host 'PyInstaller build completed.' -ForegroundColor Green

    $AppDir = Join-Path $Root 'dist\WinAutomator'
    Copy-Item README.md (Join-Path $AppDir 'README.md')
    $versionInfo = @{
        version = $Version
        python = '3.8.10'
        built_at = (Get-Date).ToUniversalTime().ToString('o')
    } | ConvertTo-Json
    Set-Content -Path (Join-Path $AppDir 'version.json') -Value $versionInfo -Encoding UTF8

    Write-Host 'Running built EXE smoke-test...' -ForegroundColor Cyan
    Invoke-SmokeWithTimeout -FilePath (Join-Path $AppDir 'WinAutomator.exe')
    Write-Host 'Built EXE smoke-test passed.' -ForegroundColor Green

    $PackageRoot = Join-Path $Root 'dist\package'
    New-Item -ItemType Directory -Force -Path $PackageRoot | Out-Null
    Copy-Item -Path $AppDir -Destination (Join-Path $PackageRoot 'WinAutomator') -Recurse -Force
    foreach ($file in @('install.ps1', 'install.cmd', 'uninstall.ps1', 'uninstall.cmd', 'README.md')) {
        Copy-Item -Path (Join-Path $Root $file) -Destination (Join-Path $PackageRoot $file) -Force
    }

    $zip = Join-Path $Root "dist\WinAutomator-$Version-win-x64.zip"
    Compress-Archive -Path (Join-Path $PackageRoot '*') -DestinationPath $zip -Force
    Write-Host "Build ready: $zip" -ForegroundColor Green
} finally {
    Pop-Location
}
