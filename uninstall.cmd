@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1" %*
set "rc=%ERRORLEVEL%"
if not "%rc%"=="0" (
  echo.
  echo Win Automator removal failed with code %rc%.
  if not defined CI pause
)
exit /b %rc%
