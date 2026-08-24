param(
    [string]$Python = '',
    [switch]$SkipBootstrap
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Offline = Join-Path $Root 'offline'
$Wheels = Join-Path $Offline 'wheels'
New-Item -ItemType Directory -Force -Path $Wheels | Out-Null

$pythonInstaller = Join-Path $Offline 'python-3.8.10-amd64.exe'
if (-not (Test-Path $pythonInstaller)) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe' -OutFile $pythonInstaller
}
$md5 = (Get-FileHash $pythonInstaller -Algorithm MD5).Hash.ToUpperInvariant()
if ($md5 -ne '62CF1A12A5276B0259E8761D4CF4FE42') { throw 'Python installer checksum mismatch.' }
$sig = Get-AuthenticodeSignature -FilePath $pythonInstaller
if ($sig.Status -ne 'Valid') { throw "Python installer signature is not valid: $($sig.Status)" }

if ([string]::IsNullOrWhiteSpace($Python)) {
    if ($SkipBootstrap) {
        $Python = (Get-Command python -ErrorAction Stop).Source
    } else {
        & (Join-Path $Root 'bootstrap.ps1') -NoRun
        $Python = Join-Path $Root '.venv\Scripts\python.exe'
    }
}
& $Python -m pip download --dest $Wheels -r (Join-Path $Root 'requirements-dev.txt')
if ($LASTEXITCODE -ne 0) { throw 'pip download failed.' }

@{
    created_at = (Get-Date).ToUniversalTime().ToString('o')
    python = '3.8.10'
    requirements_runtime = (Get-Content -Raw (Join-Path $Root 'requirements-runtime.txt')).Trim()
    requirements_dev = (Get-Content -Raw (Join-Path $Root 'requirements-dev.txt')).Trim()
} | ConvertTo-Json | Set-Content (Join-Path $Offline 'manifest.json') -Encoding UTF8

Write-Host "Offline dependencies prepared: $Offline" -ForegroundColor Green
