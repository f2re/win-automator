param(
    [Parameter(Mandatory=$true)][string]$PackagePath,
    [string]$ReportPath = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

if ([Environment]::OSVersion.Platform -ne 'Win32NT') {
    throw 'Air-gap verification is supported on Windows only.'
}
if (-not [Environment]::Is64BitOperatingSystem) {
    throw 'Air-gap verification requires Windows x64.'
}

$PackagePath = (Resolve-Path -LiteralPath $PackagePath).Path
if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    $ReportPath = Join-Path (Split-Path -Parent $PackagePath) 'AIRGAP-VERIFICATION.json'
}

$powerShellExe = (Get-Command powershell.exe -ErrorAction Stop).Source
$tempRoot = Join-Path $env:RUNNER_TEMP ("win-automator-airgap-" + [Guid]::NewGuid().ToString('N'))
$extractRoot = Join-Path $tempRoot 'extracted'
$installDir = Join-Path $tempRoot 'installed'
$rules = @()
$oldHttp = $env:HTTP_PROXY
$oldHttps = $env:HTTPS_PROXY
$oldAll = $env:ALL_PROXY
$oldNoProxy = $env:NO_PROXY
$oldPipNoIndex = $env:PIP_NO_INDEX
$oldPath = $env:PATH

function Add-OutboundBlock {
    param([Parameter(Mandatory=$true)][string]$Program)
    $name = "WinAutomator-AirGap-" + [Guid]::NewGuid().ToString('N')
    New-NetFirewallRule -DisplayName $name -Direction Outbound -Program $Program -Action Block -Profile Any | Out-Null
    $script:rules += $name
    $rule = Get-NetFirewallRule -DisplayName $name -ErrorAction Stop
    if ([string]$rule.Enabled -ne 'True') {
        throw "Firewall rule was not enabled for $Program"
    }
}

function Invoke-Smoke {
    param(
        [Parameter(Mandatory=$true)][string]$Exe,
        [Parameter(Mandatory=$true)][string]$Mode,
        [Parameter(Mandatory=$true)][string]$Version,
        [Parameter(Mandatory=$true)][string]$Prefix
    )
    $report = Join-Path $tempRoot "$Prefix-$($Mode.TrimStart('-').Replace('-','_')).json"
    Remove-Item -LiteralPath $report -Force -ErrorAction SilentlyContinue
    $p = Start-Process -FilePath $Exe -ArgumentList @($Mode, "`"$report`"") -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "$Prefix $Mode failed with exit code $($p.ExitCode)." }
    if (-not (Test-Path -LiteralPath $report)) { throw "$Prefix $Mode did not create report." }
    $data = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if (-not $data.ok) { throw "$Prefix $Mode reported failed checks." }
    if ([string]$data.version -ne $Version) { throw "$Prefix version mismatch: $($data.version) != $Version" }
}

function Invoke-LiveLaunch {
    param(
        [Parameter(Mandatory=$true)][string]$Exe,
        [Parameter(Mandatory=$true)][string]$Prefix
    )
    $p = Start-Process -FilePath $Exe -PassThru
    Start-Sleep -Seconds 3
    if ($p.HasExited) { throw "$Prefix normal GUI launch failed with exit code $($p.ExitCode)." }
    Stop-Process -Id $p.Id -Force
}

New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null

try {
    Expand-Archive -LiteralPath $PackagePath -DestinationPath $extractRoot -Force

    $manifests = @(Get-ChildItem -LiteralPath $extractRoot -Recurse -Filter 'OFFLINE-MANIFEST.json' -File)
    if ($manifests.Count -ne 1) {
        throw "Expected exactly one OFFLINE-MANIFEST.json, found $($manifests.Count)."
    }
    $bundleRoot = Split-Path -Parent $manifests[0].FullName
    $manifest = Get-Content -LiteralPath $manifests[0].FullName -Raw | ConvertFrom-Json
    $version = [string]$manifest.version

    $verifier = Join-Path $bundleRoot 'VERIFY-OFFLINE.ps1'
    if (-not (Test-Path -LiteralPath $verifier)) { throw 'Bundled VERIFY-OFFLINE.ps1 is missing.' }

    $installer = Join-Path $bundleRoot (([string]$manifest.entrypoints.installer).Replace('/', '\'))
    $portable = Join-Path $bundleRoot (([string]$manifest.entrypoints.portable).Replace('/', '\'))

    if (-not (Get-Command New-NetFirewallRule -ErrorAction SilentlyContinue)) {
        throw 'Windows Firewall PowerShell cmdlets are unavailable; strict air-gap proof cannot run.'
    }

    Add-OutboundBlock -Program $installer
    Add-OutboundBlock -Program $portable

    $env:HTTP_PROXY = 'http://127.0.0.1:9'
    $env:HTTPS_PROXY = 'http://127.0.0.1:9'
    $env:ALL_PROXY = 'http://127.0.0.1:9'
    $env:NO_PROXY = ''
    $env:PIP_NO_INDEX = '1'
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\Wbem"

    & $powerShellExe -NoProfile -ExecutionPolicy Bypass -File $verifier -Root $bundleRoot -Smoke
    if ($LASTEXITCODE -ne 0) { throw "Bundled offline verifier failed with exit code $LASTEXITCODE." }

    Remove-Item -LiteralPath $installDir -Recurse -Force -ErrorAction SilentlyContinue
    $p = Start-Process -FilePath $installer -ArgumentList @(
        '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', "/DIR=`"$installDir`""
    ) -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Offline installer failed with exit code $($p.ExitCode)." }

    $installedExe = Join-Path $installDir 'WinAutomator.exe'
    if (-not (Test-Path -LiteralPath $installedExe)) { throw "Installed EXE is missing: $installedExe" }
    Add-OutboundBlock -Program $installedExe

    foreach ($mode in @('--smoke-test', '--smoke-gui')) {
        Invoke-Smoke -Exe $installedExe -Mode $mode -Version $version -Prefix 'installed'
        Invoke-Smoke -Exe $portable -Mode $mode -Version $version -Prefix 'portable'
    }

    Invoke-LiveLaunch -Exe $installedExe -Prefix 'installed'
    Invoke-LiveLaunch -Exe $portable -Prefix 'portable'

    $uninstaller = Join-Path $installDir 'unins000.exe'
    if (-not (Test-Path -LiteralPath $uninstaller)) { throw 'Inno Setup uninstaller is missing.' }
    $p = Start-Process -FilePath $uninstaller -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Offline uninstaller failed with exit code $($p.ExitCode)." }

    $result = [PSCustomObject]@{
        schema = 1
        product = 'Win Automator'
        version = $version
        package = Split-Path -Leaf $PackagePath
        verified_at = (Get-Date).ToUniversalTime().ToString('o')
        runner = $env:RUNNER_NAME
        platform = 'windows-x64'
        network_policy = 'process-specific Windows Firewall outbound BLOCK + dead HTTP/HTTPS/ALL proxy'
        system_python_path_removed = $true
        package_manifest_verified = $true
        installer_offline_install = $true
        installed_smoke = $true
        installed_gui_smoke = $true
        installed_normal_launch = $true
        portable_smoke = $true
        portable_gui_smoke = $true
        portable_normal_launch = $true
        uninstall = $true
        network_required = $false
        system_python_required = $false
        ok = $true
    }
    $result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
    Write-Host "Strict air-gap verification passed: $PackagePath" -ForegroundColor Green
} finally {
    foreach ($name in $rules) {
        Remove-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue
    }
    $env:HTTP_PROXY = $oldHttp
    $env:HTTPS_PROXY = $oldHttps
    $env:ALL_PROXY = $oldAll
    $env:NO_PROXY = $oldNoProxy
    $env:PIP_NO_INDEX = $oldPipNoIndex
    $env:PATH = $oldPath
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
