param(
    [switch]$SkipBootstrap,
    [switch]$RequireInstaller,
    [switch]$Offline,
    [string]$Version = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Dist = Join-Path $Root 'dist'
$ProjectPython = Join-Path $Root '.venv\Scripts\python.exe'

if ($SkipBootstrap -and $Offline) {
    throw '-Offline cannot be combined with -SkipBootstrap because no offline bootstrap would be performed.'
}

function Invoke-ProcessWithTimeout {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [int]$TimeoutSeconds = 90
    )
    $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -PassThru
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        try { $process.Kill() } catch {}
        try { $process.WaitForExit() } catch {}
        throw "Process timed out after $TimeoutSeconds seconds: $FilePath $($ArgumentList -join ' ')"
    }
    if ($process.ExitCode -ne 0) {
        throw "Process failed with exit code $($process.ExitCode): $FilePath $($ArgumentList -join ' ')"
    }
    return $process
}

function New-FullOfflineBundle {
    param(
        [Parameter(Mandatory=$true)][string]$AppDir,
        [Parameter(Mandatory=$true)][string]$InstallerPath,
        [Parameter(Mandatory=$true)][string]$Version
    )

    if (-not (Test-Path -LiteralPath $InstallerPath)) {
        throw "Cannot create FULL-OFFLINE bundle: installer is missing: $InstallerPath"
    }

    $stageRoot = Join-Path $Dist 'full-offline-stage'
    $stage = Join-Path $stageRoot "WinAutomator-$Version-FULL-OFFLINE"
    $setupDir = Join-Path $stage 'setup'
    $portableDir = Join-Path $stage 'portable'
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $stageRoot
    New-Item -ItemType Directory -Force -Path $setupDir, $portableDir | Out-Null

    Copy-Item -LiteralPath $InstallerPath -Destination (Join-Path $setupDir (Split-Path -Leaf $InstallerPath)) -Force
    Copy-Item -LiteralPath $AppDir -Destination (Join-Path $portableDir 'WinAutomator') -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $Root 'scripts\verify-offline-bundle.ps1') -Destination (Join-Path $stage 'VERIFY-OFFLINE.ps1') -Force

    $installerName = Split-Path -Leaf $InstallerPath
    @"
@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0VERIFY-OFFLINE.ps1" -Smoke
if errorlevel 1 (
  echo.
  echo OFFLINE package verification FAILED. Installation stopped.
  pause
  exit /b 1
)
start /wait "" "%~dp0setup\$installerName"
exit /b %errorlevel%
"@ | Set-Content -LiteralPath (Join-Path $stage 'INSTALL.cmd') -Encoding ASCII

    @"
@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0VERIFY-OFFLINE.ps1" -Smoke
if errorlevel 1 (
  echo.
  echo OFFLINE package verification FAILED. Portable launch stopped.
  pause
  exit /b 1
)
start "" "%~dp0portable\WinAutomator\WinAutomator.exe"
"@ | Set-Content -LiteralPath (Join-Path $stage 'RUN-PORTABLE.cmd') -Encoding ASCII

    @"
Win Automator $Version - FULL OFFLINE package
================================================

This archive is intended for a Windows x64 machine with NO Internet access.

Nothing is downloaded during verification, installation or normal application startup.
System Python, pip, PyPI, winget, Chocolatey and Microsoft Excel are not required.

Recommended:
  1. Extract the whole archive.
  2. Double-click INSTALL.cmd.
  3. INSTALL.cmd verifies SHA-256 of every payload file and runs a packaged smoke test.
  4. The bundled Inno Setup installer installs Win Automator for the current user.

Portable mode:
  Double-click RUN-PORTABLE.cmd.

Manual integrity check:
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\VERIFY-OFFLINE.ps1 -Smoke

Do not copy only WinAutomator.exe from the portable directory. The complete
portable\WinAutomator directory is one application payload.
"@ | Set-Content -LiteralPath (Join-Path $stage 'README-OFFLINE.txt') -Encoding UTF8

    $payloadFiles = @()
    Get-ChildItem -LiteralPath $stage -Recurse -File |
        Where-Object { $_.Name -ne 'OFFLINE-MANIFEST.json' } |
        Sort-Object FullName |
        ForEach-Object {
            $relative = $_.FullName.Substring($stage.Length).TrimStart('\').Replace('\', '/')
            $payloadFiles += [PSCustomObject]@{
                path = $relative
                size = $_.Length
                sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            }
        }

    $manifest = [PSCustomObject]@{
        schema = 1
        bundle_type = 'full-offline'
        product = 'Win Automator'
        version = $Version
        platform = 'windows-x64'
        network_required = $false
        system_python_required = $false
        package_manager_required = $false
        created_at = (Get-Date).ToUniversalTime().ToString('o')
        entrypoints = [PSCustomObject]@{
            installer = "setup/$installerName"
            portable = 'portable/WinAutomator/WinAutomator.exe'
        }
        files = $payloadFiles
    }
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $stage 'OFFLINE-MANIFEST.json') -Encoding UTF8

    $bundlePath = Join-Path $Dist "WinAutomator-$Version-FULL-OFFLINE-win-x64.zip"
    Compress-Archive -LiteralPath $stage -DestinationPath $bundlePath -Force
    Remove-Item -LiteralPath $stageRoot -Recurse -Force
    return $bundlePath
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = (Get-Content -Raw (Join-Path $Root 'VERSION')).Trim()
}
if ($Version -notmatch '^\d+\.\d+\.\d+([\-+][0-9A-Za-z.-]+)?$') {
    throw "Некорректная версия '$Version'. Ожидается SemVer, например 0.3.1 или 0.4.0-beta.1."
}

if ($Offline -and (Test-Path $ProjectPython)) {
    Write-Host '==> Reusing verified offline virtual environment' -ForegroundColor Cyan
    $Python = $ProjectPython
} elseif (-not $SkipBootstrap) {
    $bootstrapArgs = @('-NoRun')
    if ($Offline) { $bootstrapArgs += '-Offline' }
    & (Join-Path $Root 'bootstrap.ps1') @bootstrapArgs
    if ($LASTEXITCODE -ne 0) { throw 'Bootstrap failed.' }
    $Python = $ProjectPython
} else {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

Push-Location $Root
try {
    Write-Host "==> Tests" -ForegroundColor Cyan
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }

    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $Root 'build'), $Dist
    New-Item -ItemType Directory -Force -Path $Dist | Out-Null

    Write-Host "==> PyInstaller $Version" -ForegroundColor Cyan
    & $Python -m PyInstaller --noconfirm --clean --onedir --windowed `
        --name WinAutomator `
        --paths (Join-Path $Root 'src') `
        --collect-submodules comtypes `
        --hidden-import pywinauto.controls.uiawrapper `
        app.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }

    $AppDir = Join-Path $Dist 'WinAutomator'
    Copy-Item (Join-Path $Root 'README.md') (Join-Path $AppDir 'README.md') -Force
    Copy-Item (Join-Path $Root 'CHANGELOG.md') (Join-Path $AppDir 'CHANGELOG.md') -Force
    Copy-Item (Join-Path $Root 'VERSION') (Join-Path $AppDir 'VERSION') -Force
    Copy-Item (Join-Path $Root 'docs') (Join-Path $AppDir 'docs') -Recurse -Force
    Copy-Item (Join-Path $Root 'examples') (Join-Path $AppDir 'examples') -Recurse -Force

    $gitSha = $env:GITHUB_SHA
    if ([string]::IsNullOrWhiteSpace($gitSha)) {
        try { $gitSha = (& git rev-parse HEAD 2>$null).Trim() } catch { $gitSha = '' }
    }
    $pythonVersion = (& $Python -c "import platform; print(platform.python_version())").Trim()
    @{
        name = 'Win Automator'
        version = $Version
        python = $pythonVersion
        commit = $gitSha
        built_at = (Get-Date).ToUniversalTime().ToString('o')
        platform = 'windows-x64'
        standalone = $true
        network_required = $false
    } | ConvertTo-Json | Set-Content (Join-Path $AppDir 'version.json') -Encoding UTF8

    Write-Host "==> Smoke-test packaged EXE and bundled runtime" -ForegroundColor Cyan
    $SmokeFile = Join-Path $Dist 'smoke-report.json'
    Invoke-ProcessWithTimeout -FilePath (Join-Path $AppDir 'WinAutomator.exe') `
        -ArgumentList @('--smoke-test', "`"$SmokeFile`"") -TimeoutSeconds 90 | Out-Null
    if (-not (Test-Path $SmokeFile)) { throw 'Packaged EXE did not produce smoke-test report.' }
    $smoke = Get-Content -Raw $SmokeFile | ConvertFrom-Json
    Remove-Item $SmokeFile -Force
    if (-not $smoke.ok) { throw 'Packaged runtime smoke-test reported failure.' }
    if ($smoke.version -ne $Version) {
        throw "Packaged EXE version mismatch: expected $Version, got $($smoke.version)."
    }

    Write-Host "==> Portable archive" -ForegroundColor Cyan
    $PortableZip = Join-Path $Dist "WinAutomator-$Version-win-x64.zip"
    Compress-Archive -Path $AppDir -DestinationPath $PortableZip -Force

    $iscc = $null
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) { $iscc = $command.Source }
    if (-not $iscc) {
        $candidates = @(
            (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
            (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
        )
        $iscc = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    }

    $InstallerPath = Join-Path $Dist "WinAutomator-$Version-Setup-win-x64.exe"
    if ($iscc) {
        Write-Host "==> Installer" -ForegroundColor Cyan
        & $iscc "/DAppVersion=$Version" "/DSourceDir=$AppDir" "/DOutputDir=$Dist" `
            (Join-Path $Root 'installer\WinAutomator.iss')
        if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed.' }

        Write-Host "==> FULL-OFFLINE end-user bundle" -ForegroundColor Cyan
        $FullOfflineBundle = New-FullOfflineBundle -AppDir $AppDir -InstallerPath $InstallerPath -Version $Version
        if (-not (Test-Path -LiteralPath $FullOfflineBundle)) { throw 'FULL-OFFLINE bundle was not created.' }
    } elseif ($RequireInstaller) {
        throw 'Inno Setup 6 (ISCC.exe) is required but was not found.'
    } else {
        Write-Warning 'Inno Setup not found; portable ZIP was built, installer and FULL-OFFLINE bundle were skipped.'
    }

    $assets = Get-ChildItem $Dist -File | Where-Object {
        $_.Name -like "WinAutomator-$Version-*.zip" -or
        $_.Name -like "WinAutomator-$Version-*.exe"
    }
    if (-not $assets) { throw 'No release assets were created.' }
    $hashLines = foreach ($asset in ($assets | Sort-Object Name)) {
        $hash = (Get-FileHash $asset.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $($asset.Name)"
    }
    $hashLines | Set-Content (Join-Path $Dist 'SHA256SUMS.txt') -Encoding ASCII

    Write-Host "`nRelease assets:" -ForegroundColor Green
    Get-ChildItem $Dist -File | Where-Object {
        $_.Name -match '\.(zip|exe|txt)$'
    } | Select-Object Name, Length | Format-Table -AutoSize
} finally {
    Pop-Location
}
