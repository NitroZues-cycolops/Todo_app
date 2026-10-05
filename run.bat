@echo off
REM ============================================================
REM SmartSchedule - Quick Start Script (Windows)
REM ============================================================
echo =============================================
echo   SmartSchedule - Setup ^& Run
echo =============================================
echo.

cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+ first.
    pause
    exit /b 1
)

python --version

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing dependencies...
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q

echo.
echo Setup complete!
echo.
echo Starting SmartSchedule on http://localhost:8000 ...
echo Press Ctrl+C to stop.
echo.

python -m uvicorn smartschedule.main:app --host 0.0.0.0 --port 8000 --reload
pause
