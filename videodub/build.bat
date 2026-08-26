@echo off
echo ===================================
echo   VideoDub - Docker Build Only
echo ===================================
echo.

:: Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Docker is not running. Please start Docker Desktop.
    exit /b 1
)

echo [1/3] Creating necessary directories...
if not exist backend\temp mkdir backend\temp
if not exist backend\output mkdir backend\output
if not exist backend\cookies mkdir backend\cookies
if not exist backend\data mkdir backend\data

echo.
echo [2/3] Building production images...
docker-compose build
if %errorlevel% neq 0 (
    echo Error: Docker build failed.
    exit /b 1
)

echo.
echo [3/3] Building development images...
docker-compose -f docker-compose.dev.yml build
if %errorlevel% neq 0 (
    echo Error: Docker dev build failed.
    exit /b 1
)

echo.
echo ===================================
echo   Build completed successfully!
echo ===================================
echo.
echo Images built:
docker images | findstr videodub
echo.
echo To run production:
echo   docker-compose up -d
echo   (or run docker-run.bat)
echo.
echo To run development:
echo   docker-compose -f docker-compose.dev.yml up -d
echo   (or run docker-run-dev.bat)
echo.