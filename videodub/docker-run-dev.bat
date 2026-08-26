@echo off
echo ===================================
echo   VideoDub - Docker Dev Mode
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
echo [2/3] Building Docker images (dev)...
docker-compose -f docker-compose.dev.yml build
if %errorlevel% neq 0 (
    echo Error: Docker build failed.
    exit /b 1
)

echo.
echo [3/3] Starting containers (dev)...
docker-compose -f docker-compose.dev.yml up -d
if %errorlevel% neq 0 (
    echo Error: Failed to start containers.
    exit /b 1
)

echo.
echo Waiting for services to be ready...
timeout /t 8 /nobreak >nul

docker-compose -f docker-compose.dev.yml ps

echo.
echo ===================================
echo   VideoDub is running in Dev Mode!
echo ===================================
echo.
echo Frontend:  http://localhost:5173 (with hot reload)
echo Backend:   http://localhost:8000 (with auto-reload)
echo API Docs:  http://localhost:8000/docs
echo.
echo Useful commands:
echo   View logs:        docker-compose -f docker-compose.dev.yml logs -f
echo   View backend:     docker-compose -f docker-compose.dev.yml logs -f backend
echo   View frontend:    docker-compose -f docker-compose.dev.yml logs -f frontend
echo   Stop:             docker-compose -f docker-compose.dev.yml down
echo   Stop & clean:     docker-compose -f docker-compose.dev.yml down -v
echo   Restart:          docker-compose -f docker-compose.dev.yml restart
echo   Rebuild:          docker-compose -f docker-compose.dev.yml build --no-cache
echo.
pause