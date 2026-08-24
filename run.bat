@echo off
setlocal
set ROOT=%~dp0
if not exist "%ROOT%.venv\Scripts\python.exe" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%bootstrap.ps1" -NoRun
  if errorlevel 1 exit /b %errorlevel%
)
"%ROOT%.venv\Scripts\python.exe" "%ROOT%app.py"
