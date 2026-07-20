@echo off
echo ===================================
echo   VideoDub - Docker Build ^& Run
echo ===================================
echo.

:: Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Docker is not running. Please start Docker Desktop.
    exit /b 1
)

echo [1/4] Creating necessary directories...
if not exist backend\temp mkdir backend\temp
if not exist backend\output mkdir backend\output
if not exist backend\cookies mkdir backend\cookies

echo [2/4] Building Docker images...
docker-compose build
if %errorlevel% neq 0 (
    echo Error: Docker build failed.
    exit /b 1
)

echo.
echo [3/4] Starting containers...
docker-compose up -d
if %errorlevel% neq 0 (
    echo Error: Failed to start containers.
    exit /b 1
)

echo.
echo [4/4] Waiting for services to be ready...
timeout /t 5 /nobreak >nul

:: Check if containers are running
docker-compose ps | find "Up" >nul
if %errorlevel% equ 0 (
    echo.
    echo ===================================
    echo   VideoDub dang chay trong Docker!
    echo   Frontend: http://localhost:3000
    echo   Backend:  http://localhost:8000
    echo   API Docs: http://localhost:8000/docs
    echo ===================================
    echo.
    echo Su dung 'docker-compose logs -f' de xem log
    echo Su dung 'docker-compose down' de dung
) else (
    echo.
    echo Error: Some containers failed to start.
    echo Check logs with: docker-compose logs
    exit /b 1
)