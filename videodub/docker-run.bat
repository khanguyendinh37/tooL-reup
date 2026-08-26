@echo off
echo ===================================
echo   VideoDub - Docker Build & Run
echo ===================================
echo.

:: Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Docker is not running. Please start Docker Desktop.
    exit /b 1
)

echo [1/5] Creating necessary directories...
if not exist backend\temp mkdir backend\temp
if not exist backend\output mkdir backend\output
if not exist backend\cookies mkdir backend\cookies
if not exist backend\data mkdir backend\data

echo.
echo [2/5] Building Docker images (this may take a few minutes on first run)...
docker-compose build
if %errorlevel% neq 0 (
    echo Error: Docker build failed.
    exit /b 1
)

echo.
echo [3/5] Starting containers...
docker-compose up -d
if %errorlevel% neq 0 (
    echo Error: Failed to start containers.
    exit /b 1
)

echo.
echo [4/5] Waiting for services to be healthy...
timeout /t 10 /nobreak >nul

echo.
echo [5/5] Checking container status...
docker-compose ps

echo.
echo Checking backend health...
timeout /t 5 /nobreak >nul
curl -s http://localhost:8000/api/health >nul 2>&1
if %errorlevel% equ 0 (
    echo Backend: HEALTHY (http://localhost:8000)
) else (
    echo Backend: Starting... (check logs with: docker-compose logs -f backend)
)

curl -s http://localhost:3000 >nul 2>&1
if %errorlevel% equ 0 (
    echo Frontend: HEALTHY (http://localhost:3000)
) else (
    echo Frontend: Starting... (check logs with: docker-compose logs -f frontend)
)

echo.
echo ===================================
echo   VideoDub is running in Docker!
echo ===================================
echo.
echo Frontend:  http://localhost:3000
echo Backend:   http://localhost:8000
echo API Docs:  http://localhost:8000/docs
echo.
echo Useful commands:
echo   View logs:     docker-compose logs -f
echo   View backend:  docker-compose logs -f backend
echo   View frontend: docker-compose logs -f frontend
echo   Stop:          docker-compose down
echo   Stop & clean:  docker-compose down -v
echo   Restart:       docker-compose restart
echo.