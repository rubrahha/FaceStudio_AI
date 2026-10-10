@echo off
cd /d "%~dp0"
title FaceStudio AI - Live Camera
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0LAUNCH.ps1"
if errorlevel 1 (
  echo.
  echo FaceStudio could not start. Read the error above.
  pause
)
