@echo off
echo ========================================
echo   VideoDub Frontend - Development Server
echo ========================================
echo.

echo [1/2] Checking Node.js environment...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Node.js not found in PATH!
    echo Please install Node.js from https://nodejs.org
    pause
    exit /b 1
)

echo [2/2] Installing dependencies and starting Vite dev server...
echo.
echo Frontend will be available at: http://localhost:5173
echo Backend API proxied to: http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo ========================================
call npm ci
if %errorlevel% neq 0 (
    echo Error: npm ci failed!
    pause
    exit /b 1
)
npm run dev -- --force --host 127.0.0.1 --port 5173 --strictPort
pause
