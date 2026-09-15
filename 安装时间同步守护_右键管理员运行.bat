@echo off
rem ============================================
rem  Install "time sync guard" as SYSTEM scheduled task
rem  Fixes: QQ sendMsg "network error"(1006514) / NapCat [ServerTime]
rem  Usage: RIGHT-CLICK this file -> Run as administrator (once only)
rem  Uninstall: schtasks /Delete /TN "AIPetTimeSyncGuard" /F
rem ============================================

rem --- check administrator rights first ---
net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo [NOT ADMIN] Please RIGHT-CLICK this file and select
    echo             "Run as administrator" from the popup menu.
    echo.
    pause
    exit /b 1
)

echo [OK] Running as administrator. Installing scheduled task ...
echo.

schtasks /Create /TN "AIPetTimeSyncGuard" /TR "\"%~dp0time_sync_guard_runner.bat\"" /SC MINUTE /MO 3 /RU SYSTEM /RL HIGHEST /F

if errorlevel 1 (
    echo.
    echo [FAILED] Create task failed. Error shown above.
    pause
    exit /b 1
)

echo Starting guard now...
schtasks /Run /TN "AIPetTimeSyncGuard"

echo.
echo ============================================
echo  [OK] Installed successfully!
echo       The guard runs every 3 minutes automatically.
echo       Log file: data\time_sync_guard.log
echo       Uninstall: schtasks /Delete /TN "AIPetTimeSyncGuard" /F
echo ============================================
pause
