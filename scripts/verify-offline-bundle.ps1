param(
    [string]$Root = '',
    [switch]$Smoke
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

if ([Environment]::OSVersion.Platform -ne 'Win32NT') {
    throw 'FULL-OFFLINE verification is supported on Windows only.'
}
if (-not [Environment]::Is64BitOperatingSystem) {
    throw 'Win Automator FULL-OFFLINE package requires Windows x64.'
}

if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$Root = (Resolve-Path -LiteralPath $Root).Path
$manifestPath = Join-Path $Root 'OFFLINE-MANIFEST.json'
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "OFFLINE-MANIFEST.json is missing: $manifestPath"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ([string]$manifest.bundle_type -ne 'full-offline') {
    throw "Unexpected bundle type: $($manifest.bundle_type)"
}
if ($manifest.network_required -ne $false) {
    throw 'Bundle manifest does not declare network_required=false.'
}
if ($manifest.system_python_required -ne $false) {
    throw 'Bundle manifest does not declare system_python_required=false.'
}

$files = @($manifest.files)
if ($files.Count -lt 10) {
    throw "Offline manifest has too few payload files: $($files.Count)"
}

foreach ($item in $files) {
    $relative = ([string]$item.path).Replace('/', '\')
    if ($relative -match '(^|\\)\.\.(\\|$)') {
        throw "Unsafe manifest path: $relative"
    }
    $path = Join-Path $Root $relative
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Offline payload file is missing: $relative"
    }
    $length = (Get-Item -LiteralPath $path).Length
    if ($length -ne [int64]$item.size) {
        throw "Offline payload size mismatch for ${relative}: $length != $($item.size)"
    }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    $expected = ([string]$item.sha256).ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "Offline payload SHA256 mismatch for ${relative}: $actual != $expected"
    }
}

$installer = Join-Path $Root (([string]$manifest.entrypoints.installer).Replace('/', '\'))
$portable = Join-Path $Root (([string]$manifest.entrypoints.portable).Replace('/', '\'))
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    throw "Bundled installer is missing: $installer"
}
if (-not (Test-Path -LiteralPath $portable -PathType Leaf)) {
    throw "Bundled portable executable is missing: $portable"
}

$forbidden = @(
    Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction Stop |
        Where-Object {
            $_.Name -ieq 'python.exe' -or
            $_.Name -ieq 'pip.exe' -or
            $_.FullName -match '\\\.venv\\' -or
            $_.FullName -match '\\offline\\wheels\\'
        }
)
if ($forbidden.Count -gt 0) {
    throw "End-user FULL-OFFLINE bundle unexpectedly contains developer runtime/package-manager payload: $($forbidden[0].FullName)"
}

if ($Smoke) {
    $reportPath = Join-Path $env:TEMP ("WinAutomator-offline-smoke-" + [Guid]::NewGuid().ToString('N') + '.json')
    try {
        $process = Start-Process -FilePath $portable -ArgumentList @('--smoke-test', "`"$reportPath`"") -Wait -PassThru
        if ($process.ExitCode -ne 0) {
            throw "Portable packaged smoke-test failed with exit code $($process.ExitCode)."
        }
        if (-not (Test-Path -LiteralPath $reportPath)) {
            throw 'Portable packaged smoke-test did not create a report.'
        }
        $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
        if (-not $report.ok) {
            throw 'Portable packaged smoke-test reported failed checks.'
        }
        if ([string]$report.version -ne [string]$manifest.version) {
            throw "Portable version mismatch: $($report.version) != $($manifest.version)"
        }
    } finally {
        Remove-Item -LiteralPath $reportPath -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "FULL-OFFLINE verification passed: Win Automator $($manifest.version)" -ForegroundColor Green
Write-Host "Files verified: $($files.Count)" -ForegroundColor Green
Write-Host 'Network required: NO' -ForegroundColor Green
Write-Host 'System Python required: NO' -ForegroundColor Green
