@echo off
setlocal

set PORT=%~1
if "%PORT%"=="" set PORT=8199
if /I "%PORT%"=="-Port" set PORT=%~2
if /I "%PORT%"=="--port" set PORT=%~2
if "%PORT%"=="" set PORT=8199

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-dev.ps1" -Port %PORT%
