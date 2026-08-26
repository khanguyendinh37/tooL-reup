@echo off
echo ========================================
echo   VideoDub - Stop Docker Containers
echo ========================================
echo.

echo Checking for running containers...
docker-compose ps -q >nul 2>&1
docker-compose -f docker-compose.dev.yml ps -q >nul 2>&1

echo.
echo Stopping production containers (if running)...
docker-compose down

echo.
echo Stopping development containers (if running)...
docker-compose -f docker-compose.dev.yml down

echo.
echo ========================================
echo   All VideoDub containers stopped!
echo ========================================
echo.
echo To remove volumes as well (will delete database data):
echo   docker-compose down -v
echo   docker-compose -f docker-compose.dev.yml down -v
echo ========================================
pause