@echo off
echo ===================================
echo   VideoDub - Deploy to Server
echo ===================================
echo.

:: ===== CONFIGURATION - EDIT THIS =====
set DOCKERHUB_USERNAME=your-dockerhub-username
set SERVER_USER=root
set SERVER_IP=your-server-ip
set SERVER_PATH=/opt/videodub
:: =====================================

if "%DOCKERHUB_USERNAME%"=="your-dockerhub-username" (
    echo ERROR: Chua cau hinh DOCKERHUB_USERNAME!
    pause
    exit /b 1
)
if "%SERVER_IP%"=="your-server-ip" (
    echo ERROR: Chua cau hinh SERVER_IP!
    pause
    exit /b 1
)

echo [1/4] Tao docker-compose.prod.yml cho server...
(
    echo version: '3.8'
    echo.
    echo services:
    echo   backend:
    echo     image: %DOCKERHUB_USERNAME%/videodub-backend:latest
    echo     container_name: videodub-backend
    echo     ports:
    echo       - "8000:8000"
    echo     volumes:
    echo       - ./backend/temp:/app/temp
    echo       - ./backend/output:/app/output
    echo       - ./backend/cookies:/app/cookies
    echo       - backend_data:/app/data
    echo     environment:
    echo       - DATABASE_URL=sqlite+aiosqlite:///./data/videodub.db
    echo     restart: unless-stopped
    echo.
    echo   frontend:
    echo     image: %DOCKERHUB_USERNAME%/videodub-frontend:latest
    echo     container_name: videodub-frontend
    echo     ports:
    echo       - "3000:80"
    echo     depends_on:
    echo       - backend
    echo     restart: unless-stopped
    echo.
    echo volumes:
    echo   backend_data:
) > docker-compose.prod.yml

echo [2/4] Copy file len server...
scp docker-compose.prod.yml %SERVER_USER%@%SERVER_IP%:%SERVER_PATH%/docker-compose.yml
if %errorlevel% neq 0 (
    echo Copy that bai. Kiem tra SSH key/password.
    exit /b 1
)

echo [3/4] Tao thu muc tren server...
ssh %SERVER_USER%@%SERVER_IP% "mkdir -p %SERVER_PATH%/backend/temp %SERVER_PATH%/backend/output %SERVER_PATH%/backend/cookies %SERVER_PATH%/backend/data"

echo [4/4] Deploy tren server...
ssh %SERVER_USER%@%SERVER_IP% "cd %SERVER_PATH% && docker-compose pull && docker-compose up -d"
if %errorlevel% neq 0 (
    echo Deploy that bai!
    exit /b 1
)

echo.
echo ===================================
echo   DEPLOY THANH CONG!
echo ===================================
echo.
echo Server: http://%SERVER_IP%:3000
echo API:    http://%SERVER_IP%:8000
echo Docs:   http://%SERVER_IP%:8000/docs
echo.
pause