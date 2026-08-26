@echo off
echo ===================================
echo   VideoDub - Push to Docker Hub
echo ===================================
echo.

:: ===== CONFIGURATION - EDIT THIS =====
set DOCKERHUB_USERNAME=your-dockerhub-username
set IMAGE_TAG=latest
:: =====================================

if "%DOCKERHUB_USERNAME%"=="your-dockerhub-username" (
    echo ERROR: Chua cau hinh DOCKERHUB_USERNAME!
    echo.
    echo Mo file nay va sua dong:
    echo   set DOCKERHUB_USERNAME=your-dockerhub-username
    echo.
    echo Thanh: ten_dang_nhap_cua_ban_tren_dockerhub
    echo.
    pause
    exit /b 1
)

echo [1/5] Kiem tra Docker login...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker chua chay. Khoi dong Docker Desktop.
    exit /b 1
)

docker logout >nul 2>&1
echo Dang nhap Docker Hub...
docker login
if %errorlevel% neq 0 (
    echo Dang nhap that bai.
    exit /b 1
)

echo.
echo [2/5] Tao builder multi-platform (amd64/arm64)...
docker buildx create --name videodub-builder --use --bootstrap 2>nul || docker buildx use videodub-builder

echo.
echo [3/5] Build & Push BACKEND (multi-arch)...
docker buildx build ^
    --platform linux/amd64,linux/arm64 ^
    -t %DOCKERHUB_USERNAME%/videodub-backend:%IMAGE_TAG% ^
    -f backend/Dockerfile ^
    ./backend ^
    --push
if %errorlevel% neq 0 (
    echo Build backend that bai!
    exit /b 1
)

echo.
echo [4/5] Build & Push FRONTEND (multi-arch)...
docker buildx build ^
    --platform linux/amd64,linux/arm64 ^
    -t %DOCKERHUB_USERNAME%/videodub-frontend:%IMAGE_TAG% ^
    -f frontend/Dockerfile ^
    ./frontend ^
    --push
if %errorlevel% neq 0 (
    echo Build frontend that bai!
    exit /b 1
)

echo.
echo [5/5] Tao va push docker-compose.yml cho production...
:: Tao file compose de deploy tren server
(
    echo version: '3.8'
    echo.
    echo services:
    echo   backend:
    echo     image: %DOCKERHUB_USERNAME%/videodub-backend:%IMAGE_TAG%
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
    echo     image: %DOCKERHUB_USERNAME%/videodub-frontend:%IMAGE_TAG%
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

echo.
echo ===================================
echo   HOAN TAT PUSH LEN DOCKER HUB!
echo ===================================
echo.
echo Images da push:
echo   %DOCKERHUB_USERNAME%/videodub-backend:%IMAGE_TAG%
echo   %DOCKERHUB_USERNAME%/videodub-frontend:%IMAGE_TAG%
echo.
echo File deploy tao ra: docker-compose.prod.yml
echo.
echo Tren server, chi can chay:
echo   docker-compose -f docker-compose.prod.yml up -d
echo.
pause