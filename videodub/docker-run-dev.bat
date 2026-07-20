@echo off
echo ===================================
echo   VideoDub - Docker Dev Mode
echo ===================================
echo.

echo [1/3] Building Docker images (dev)...
docker-compose -f docker-compose.dev.yml build

echo.
echo [2/3] Starting containers (dev)...
docker-compose -f docker-compose.dev.yml up -d

echo.
echo [3/3] Done!
echo.
echo ===================================
echo   VideoDub dang chay trong Docker Dev Mode!
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo ===================================
echo.
echo Su dung 'docker-compose -f docker-compose.dev.yml logs -f' de xem log
echo Su dung 'docker-compose -f docker-compose.dev.yml down' de dung
pause