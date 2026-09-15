@echo off
rem time sync guard runner (called by scheduled task every 3 min)
cd /d "%~dp0"

set "PYW="
if exist "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\pythonw.exe" set "PYW=C:\Users\Administrator\AppData\Local\Programs\Python\Python310\pythonw.exe"
if not defined PYW if exist "%~dp0runtime\venv\Scripts\pythonw.exe" set "PYW=%~dp0runtime\venv\Scripts\pythonw.exe"
if not defined PYW exit /b 1

start "" /b "%PYW%" "%~dp0time_sync_guard.py"
exit /b 0
