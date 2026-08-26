@echo off
echo ===================================
echo   VideoDub - Stop Docker Containers
echo ===================================
echo.

echo Stopping production containers...
docker-compose down
if %errorlevel% neq 0 (
    echo No production containers running or error stopping.
)

echo.
echo Stopping development containers...
docker-compose -f docker-compose.dev.yml down
if %errorlevel% neq 0 (
    echo No development containers running or error stopping.
)

echo.
echo All containers stopped.
echo.
echo To also remove volumes (data loss!):
echo   docker-compose down -v
echo   docker-compose -f docker-compose.dev.yml down -v
echo.
pause