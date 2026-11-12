@echo off
setlocal enabledelayedexpansion

title Gold & Silver Quantitative Intelligence Terminal (Launch Engine)

echo ===============================================================================
echo  GOLD & SILVER QUANTITATIVE INTELLIGENCE TERMINAL v8.0 (PRODUCTION)
echo  MCX Institutional Quantitative Research & Forecasting System
echo ===============================================================================
echo.

:: 1. Navigate to script directory
cd /d "%~dp0"
echo [*] Working Directory: %CD%

:: 2. Set environment parameters
set MPLCONFIGDIR=%TEMP%\mpl
if not exist "%TEMP%\mpl" mkdir "%TEMP%\mpl"
set PYTHONIOENCODING=utf-8
set STREAMLIT_SERVER_HEADLESS=true
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
set STREAMLIT_THEME_BASE=dark

:: 3. Verify Python installation
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in system PATH.
    echo Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo [*] Detected Python Runtime: %PY_VER%

:: 4. Verify Critical Project Dependencies
echo [*] Verifying critical dependencies (streamlit, pandas, plotly, sqlite3)...
python -c "import streamlit, pandas, plotly, sqlite3; print('    -> Core dependencies verified OK')"
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Missing dependencies. Attempting to install from requirements.txt...
    python -m pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install required packages.
        pause
        exit /b 1
    )
)

:: 5. Launch Browser & Streamlit Server
echo.
echo ===============================================================================
echo  STARTING STREAMLIT FINANCIAL TERMINAL ON http://localhost:8501
echo  Press Ctrl+C in this console or run STOP_GOLD_SILVER_TERMINAL.bat to exit.
echo ===============================================================================
echo.

:: Launch default browser after 2-second delay in background
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8501"

:: Start Streamlit server
python -m streamlit run app.py --server.port=8501 --server.address=localhost --browser.serverAddress=localhost

pause
