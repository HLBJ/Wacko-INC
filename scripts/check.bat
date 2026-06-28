@echo off
setlocal
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0check.ps1" %*
