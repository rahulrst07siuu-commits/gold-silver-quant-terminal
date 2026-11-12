@echo off
setlocal enabledelayedexpansion

title Gold & Silver Quantitative Intelligence Terminal (Portable Launcher)

echo ===============================================================================
echo   GOLD & SILVER QUANTITATIVE INTELLIGENCE TERMINAL (PORTABLE RUNNER)
echo   MCX Algorithmic Research, Multi-Horizon AI Forecasting & Paper Trading
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
echo [*] Checking Python environment...
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Python is not installed or not added to your system PATH!
    echo.
    echo Please install Python 3.10, 3.11, 3.12, 3.13, or 3.14:
    echo   1. Download Python from: https://www.python.org/downloads/
    echo   2. IMPORTANT: Check the box "Add python.exe to PATH" during installation.
    echo   3. Once installed, re-run this file!
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo [*] Detected Python Runtime: %PY_VER%

:: 4. Optional: Virtual environment support
if exist ".venv\Scripts\activate.bat" (
    echo [*] Activating local virtual environment (.venv)...
    call .venv\Scripts\activate.bat
)

:: 5. Verify Critical Project Dependencies
echo [*] Verifying dependencies (streamlit, pandas, plotly, scikit-learn, etc.)...
python -c "import streamlit, pandas, plotly, sklearn, sqlite3; print('    -> Core quantitative packages verified successfully.')" 2>nul
if %ERRORLEVEL% neq 0 (
    echo [!] Installing/Updating required packages from requirements.txt...
    echo [*] This only happens once on a new computer. Please wait a moment...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install dependencies. Check your internet connection.
        pause
        exit /b 1
    )
    echo [*] All requirements installed successfully!
)

:: 6. Launch Browser & Streamlit Server
echo.
echo ===============================================================================
echo  STARTING APPLICATION TERMINAL
echo  Terminal URL: http://localhost:8501
echo  Press Ctrl+C in this console window to stop the server anytime.
echo ===============================================================================
echo.

:: Launch browser in background after 2 seconds
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8501"

:: Launch Streamlit server
python -m streamlit run app.py --server.port=8501 --server.address=localhost --browser.serverAddress=localhost

pause
