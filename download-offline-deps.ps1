$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Offline = Join-Path $Root 'offline'
$Wheels = Join-Path $Offline 'wheels'
$PythonInstaller = Join-Path $Offline 'python-3.8.10-amd64.exe'
$ExpectedSha256 = '7628244CB53408B50639D2C1287C659F4E29D3DFDB9084B11AED5870C0C6A48A'
$BootstrapPackages = @('pip==24.3.1', 'setuptools==75.3.2', 'wheel==0.45.1')

function Invoke-Checked {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')" }
}

if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'This script is for Windows only.' }
if (-not [Environment]::Is64BitOperatingSystem) { throw 'Offline bundle is built for Windows x64.' }

if (Test-Path $Wheels) { Remove-Item -Recurse -Force $Wheels }
New-Item -ItemType Directory -Force -Path $Wheels | Out-Null

if (-not (Test-Path $PythonInstaller)) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe' -OutFile $PythonInstaller
}
$sha = (Get-FileHash -LiteralPath $PythonInstaller -Algorithm SHA256).Hash.ToUpperInvariant()
if ($sha -ne $ExpectedSha256) { throw "Python installer SHA256 mismatch: $sha" }
$sig = Get-AuthenticodeSignature -FilePath $PythonInstaller
if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate -eq $null -or $sig.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
    throw "Python installer signature is not valid: $($sig.Status)"
}

# Online bootstrap is used only on the connected preparation machine.
& (Join-Path $Root 'bootstrap.ps1') -NoRun
if ($LASTEXITCODE -ne 0) { throw 'Online bootstrap failed.' }
$Python = Join-Path $Root '.venv\Scripts\python.exe'

Invoke-Checked $Python '-m' 'pip' 'download' '--only-binary=:all:' '--dest' $Wheels @BootstrapPackages '-r' (Join-Path $Root 'requirements-dev.txt')

# Generate a SHA256 manifest for every payload file. The manifest itself is
# excluded and regenerated on each bundle build.
$files = @()
Get-ChildItem -LiteralPath $Offline -Recurse -File | Where-Object { $_.Name -ne 'manifest.json' } | Sort-Object FullName | ForEach-Object {
    $relative = $_.FullName.Substring($Offline.Length).TrimStart('\').Replace('\', '/')
    $files += [PSCustomObject]@{
        path = $relative
        size = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
$manifest = [PSCustomObject]@{
    version = 1
    python = '3.8.10-amd64'
    created_at = (Get-Date).ToUniversalTime().ToString('o')
    files = $files
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $Offline 'manifest.json') -Encoding UTF8

Write-Host "Offline bundle is ready and verified: $Offline" -ForegroundColor Green
Write-Host "Manifest payload files: $($files.Count)" -ForegroundColor Green
