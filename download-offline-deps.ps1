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

& (Join-Path $Root 'bootstrap.ps1') -NoRun
$python = Join-Path $Root '.venv\Scripts\python.exe'
& $python -m pip download --dest $Wheels -r (Join-Path $Root 'requirements-dev.txt')
Write-Host "Offline bundle подготовлен: $Offline" -ForegroundColor Green
