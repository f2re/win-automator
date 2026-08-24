param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Version
)

$ErrorActionPreference = 'Stop'
if ($Version -notmatch '^\d+\.\d+\.\d+([\-+][0-9A-Za-z.-]+)?$') {
    throw "Некорректная SemVer-версия: $Version"
}

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Content -Path (Join-Path $Root 'VERSION') -Value $Version -Encoding ASCII
Write-Host "VERSION -> $Version" -ForegroundColor Green
Write-Host "Добавьте запись в CHANGELOG.md, затем commit + push в main." -ForegroundColor Yellow
