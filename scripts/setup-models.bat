@echo off
setlocal
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0setup-models.ps1" %*
