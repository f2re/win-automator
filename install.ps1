param(
    [string]$SourceDir = (Join-Path $PSScriptRoot 'WinAutomator'),
    [string]$InstallDir = '',
    [switch]$NoShortcut,
    [switch]$NoLaunch
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Write-Step([string]$Text) { Write-Host "`n==> $Text" -ForegroundColor Cyan }

function Invoke-SmokeWithTimeout {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [int]$TimeoutSeconds = 30
    )
    $process = Start-Process -FilePath $FilePath -ArgumentList '--smoke-test' -PassThru
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        try { $process.Kill() } catch {}
        try { $process.WaitForExit() } catch {}
        throw "Smoke-test timed out after $TimeoutSeconds seconds: $FilePath"
    }
    if ($process.ExitCode -ne 0) {
        throw "Smoke-test failed with exit code $($process.ExitCode): $FilePath"
    }
}

if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'Installer is for Windows only.' }
if (-not [Environment]::Is64BitOperatingSystem) { throw 'Win Automator requires Windows x64.' }

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    $local = $env:LOCALAPPDATA
    if ([string]::IsNullOrWhiteSpace($local)) { $local = Join-Path $env:USERPROFILE 'AppData\Local' }
    $InstallDir = Join-Path $local 'Programs\WinAutomator'
}

$SourceDir = [IO.Path]::GetFullPath($SourceDir)
$InstallDir = [IO.Path]::GetFullPath($InstallDir)
$SourceExe = Join-Path $SourceDir 'WinAutomator.exe'
if (-not (Test-Path -LiteralPath $SourceExe)) { throw "WinAutomator.exe is missing from package: $SourceExe" }

$running = Get-Process -Name 'WinAutomator' -ErrorAction SilentlyContinue
if ($running) { throw 'Win Automator is already running. Close it before install/update.' }

$parent = Split-Path -Parent $InstallDir
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$staging = "$InstallDir.new.$PID"
$backup = "$InstallDir.old.$PID"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $staging, $backup
New-Item -ItemType Directory -Force -Path $staging | Out-Null

Write-Step 'Copying application files'
Copy-Item -Path (Join-Path $SourceDir '*') -Destination $staging -Recurse -Force

$StagedExe = Join-Path $staging 'WinAutomator.exe'
Write-Step 'Verifying staged application'
try {
    Invoke-SmokeWithTimeout -FilePath $StagedExe
} catch {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $staging
    throw
}

Write-Step 'Installing atomically'
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
Write-Step 'Verifying installed application'
try {
    Invoke-SmokeWithTimeout -FilePath $InstalledExe
} catch {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $InstallDir
    if (Test-Path -LiteralPath $backup) { Move-Item -LiteralPath $backup -Destination $InstallDir }
    throw
}
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $backup

if (-not $NoShortcut) {
    Write-Step 'Creating shortcuts'
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

Write-Host "`nWin Automator installed: $InstallDir" -ForegroundColor Green
if (-not $NoLaunch) {
    Write-Step 'Starting Win Automator'
    Start-Process -FilePath $InstalledExe -WorkingDirectory $InstallDir | Out-Null
}
