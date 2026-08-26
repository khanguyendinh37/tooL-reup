@echo off
echo ========================================
echo   VideoDub Backend - Development Server
echo ========================================
echo.

echo [1/2] Checking Python environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python not found in PATH!
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

if not defined VIDEODUB_DATA_DIR set "VIDEODUB_DATA_DIR=%LOCALAPPDATA%\VideoDub"
if not exist "%VIDEODUB_DATA_DIR%" mkdir "%VIDEODUB_DATA_DIR%"

echo [2/2] Installing dependencies and starting FastAPI server...
echo.
echo Backend API will be available at: http://localhost:8000
echo API Documentation (Swagger): http://localhost:8000/docs
echo API Documentation (ReDoc): http://localhost:8000/redoc
echo Health check: http://localhost:8000/api/health
echo.
echo Press Ctrl+C to stop the server
echo ========================================
pip install -r requirements.txt --quiet 2>nul
python -m uvicorn app.main:app --reload --port 8000
pause
