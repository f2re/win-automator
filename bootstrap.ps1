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
$ExpectedSha256 = '7628244CB53408B50639D2C1287C659F4E29D3DFDB9084B11AED5870C0C6A48A'
$BootstrapPackages = @('pip==24.3.1', 'setuptools==75.3.2', 'wheel==0.45.1')

function Write-Step([string]$Text) { Write-Host "`n==> $Text" -ForegroundColor Cyan }

function Invoke-Checked {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

function Test-OfflineManifest {
    $offlineRoot = Join-Path $Root 'offline'
    $manifestPath = Join-Path $offlineRoot 'manifest.json'
    if (-not (Test-Path $manifestPath)) {
        throw "Offline manifest is missing: $manifestPath. Run download-offline-deps.ps1 first."
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    foreach ($item in @($manifest.files)) {
        $filePath = Join-Path $offlineRoot ([string]$item.path)
        if (-not (Test-Path -LiteralPath $filePath)) { throw "Offline file is missing: $($item.path)" }
        $actual = (Get-FileHash -LiteralPath $filePath -Algorithm SHA256).Hash.ToUpperInvariant()
        if ($actual -ne ([string]$item.sha256).ToUpperInvariant()) {
            throw "Offline file integrity check failed for $($item.path): $actual"
        }
    }
}

function Test-PythonInstaller([string]$Path, [switch]$RequireValidSignature) {
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($actual -ne $ExpectedSha256) {
        throw "Python installer SHA256 mismatch: $actual"
    }
    $sig = Get-AuthenticodeSignature -FilePath $Path
    if ($sig.SignerCertificate -eq $null -or $sig.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
        throw 'Python installer is not signed by Python Software Foundation.'
    }
    if ($RequireValidSignature -and $sig.Status -ne 'Valid') {
        throw "Python installer signature is not valid: $($sig.Status)"
    }
}

if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'This bootstrap is for Windows only.' }
if (-not [Environment]::Is64BitOperatingSystem) { throw 'Win Automator prototype requires Windows x64.' }

New-Item -ItemType Directory -Force -Path $Downloads | Out-Null

if ($Offline) {
    Write-Step 'Verifying offline bundle integrity'
    Test-OfflineManifest
}

$runtimeOk = $false
if (Test-Path $Python) {
    try {
        # Deliberately avoid quotes inside the python -c payload: Windows PowerShell 5.1
        # strips nested quotes when passing native-process arguments.
        $versionProbe = 'import platform,sys; print(sys.version_info[0],sys.version_info[1],sys.version_info[2],platform.architecture()[0])'
        $detected = (& $Python -c $versionProbe).Trim()
        $runtimeOk = ($LASTEXITCODE -eq 0 -and $detected -eq '3 8 10 64bit')
    } catch {
        $runtimeOk = $false
    }
}
if (-not $runtimeOk) {
    if (Test-Path $RuntimeRoot) { Remove-Item -Recurse -Force $RuntimeRoot }
    if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
    New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

    Write-Step 'Preparing Python 3.8.10 x64'
    $OfflineInstaller = Join-Path $Root 'offline\python-3.8.10-amd64.exe'
    if ($Offline) {
        if (-not (Test-Path $OfflineInstaller)) { throw "Offline installer is missing: $OfflineInstaller" }
        Copy-Item $OfflineInstaller $Installer -Force
        Test-PythonInstaller -Path $Installer
    } else {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri $PythonUrl -OutFile $Installer
        Test-PythonInstaller -Path $Installer -RequireValidSignature
    }

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
    if ($p.ExitCode -ne 0 -or -not (Test-Path $Python)) { throw "Python installer failed with exit code $($p.ExitCode)" }
}

Write-Step 'Creating virtual environment'
if (-not (Test-Path $VenvPython)) { Invoke-Checked $Python '-m' 'venv' $Venv }

Write-Step 'Preparing pip/setuptools/wheel'
$OfflineWheels = Join-Path $Root 'offline\wheels'
if ($Offline) {
    if (-not (Test-Path $OfflineWheels)) { throw "Offline wheels are missing: $OfflineWheels" }
    Invoke-Checked $VenvPython '-m' 'pip' 'install' '--disable-pip-version-check' '--no-index' '--find-links' $OfflineWheels @BootstrapPackages
} else {
    Invoke-Checked $VenvPython '-m' 'pip' 'install' '--disable-pip-version-check' @BootstrapPackages
}

Write-Step 'Installing project dependencies'
if ($Offline) {
    Invoke-Checked $VenvPython '-m' 'pip' 'install' '--disable-pip-version-check' '--no-index' '--find-links' $OfflineWheels '-r' (Join-Path $Root 'requirements-dev.txt')
} else {
    Invoke-Checked $VenvPython '-m' 'pip' 'install' '--disable-pip-version-check' '-r' (Join-Path $Root 'requirements-dev.txt')
}

Write-Step 'Running environment self-test'
Invoke-Checked $VenvPython (Join-Path $Root 'scripts\self_test.py')

if (-not $NoRun) {
    Write-Step 'Starting Win Automator'
    Invoke-Checked $VenvPython (Join-Path $Root 'app.py')
}
