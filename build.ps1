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

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = (Get-Content -Raw (Join-Path $Root 'VERSION')).Trim()
}
if ($Version -notmatch '^\d+\.\d+\.\d+([\-+][0-9A-Za-z.-]+)?$') {
    throw "Некорректная версия '$Version'. Ожидается SemVer, например 0.2.1 или 0.3.0-beta.1."
}

if ($Offline -and (Test-Path $ProjectPython)) {
    # A preceding bootstrap.ps1 -Offline has already verified the manifest and
    # installed the pinned wheel set. Reuse it instead of reinstalling the
    # same environment before every offline build.
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

    if ($iscc) {
        Write-Host "==> Installer" -ForegroundColor Cyan
        & $iscc "/DAppVersion=$Version" "/DSourceDir=$AppDir" "/DOutputDir=$Dist" `
            (Join-Path $Root 'installer\WinAutomator.iss')
        if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed.' }
    } elseif ($RequireInstaller) {
        throw 'Inno Setup 6 (ISCC.exe) is required but was not found.'
    } else {
        Write-Warning 'Inno Setup not found; portable ZIP was built, installer was skipped.'
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
