@echo off
setlocal enabledelayedexpansion

title Gold & Silver Quantitative Intelligence Terminal (Shutdown)

echo ===============================================================================
echo  STOPPING GOLD & SILVER QUANTITATIVE INTELLIGENCE TERMINAL
echo ===============================================================================
echo.

set KILLED=0

:: 1. Search for processes bound to port 8501
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /r ":8501.*LISTENING"') do (
    set PID=%%a
    if defined PID (
        echo [*] Found terminal process listening on port 8501 (PID: !PID!)
        taskkill /F /PID !PID! >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            echo [SUCCESS] Terminated Streamlit terminal process (PID: !PID!).
            set KILLED=1
        )
    )
)

:: 2. Also search for any orphaned streamlit python processes if needed
for /f "tokens=2 delims=," %%p in ('wmic process where "name='python.exe' and CommandLine like '%%streamlit%%app.py%%'" get ProcessId /format:csv ^| findstr /r /v "Node"') do (
    for /f "tokens=*" %%x in ("%%p") do (
        set APPPID=%%x
        if defined APPPID (
            echo [*] Found Streamlit app.py worker process (PID: !APPPID!)
            taskkill /F /PID !APPPID! >nul 2>&1
            set KILLED=1
        )
    )
)

if %KILLED% equ 0 (
    echo [INFO] No active Streamlit terminal processes detected on port 8501.
) else (
    echo.
    echo [SUCCESS] Terminal server stopped gracefully.
)

echo.
pause
