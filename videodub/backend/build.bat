@echo off
echo ========================================
echo   VideoDub Backend - Build Script
echo ========================================
echo.

echo [1/3] Checking Python environment...
python --version
if %errorlevel% neq 0 (
    echo Error: Python not found. Please install Python 3.11+
    exit /b 1
)

echo.
echo [2/3] Installing/upgrading pip and dependencies...
pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Error: Failed to install dependencies
    exit /b 1
)

echo.
echo [3/3] Creating necessary directories...
if not exist "temp" mkdir temp
if not exist "output" mkdir output
if not exist "cookies" mkdir cookies
if not exist "data" mkdir data

echo.
echo ========================================
echo   Backend build completed successfully!
echo.
echo To run the backend server, use:
echo   run.bat
echo.
echo Or run directly:
echo   python -m uvicorn app.main:app --reload --port 8000
echo ========================================
pause