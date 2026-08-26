@echo off
echo ========================================
echo   VideoDub Frontend - Build Script
echo ========================================
echo.

echo [1/3] Installing dependencies...
npm install
if %errorlevel% neq 0 (
    echo Error: npm install failed
    exit /b 1
)

echo.
echo [2/3] Building for production...
npm run build
if %errorlevel% neq 0 (
    echo Error: Build failed
    exit /b 1
)

echo.
echo [3/3] Build completed successfully!
echo.
echo Output directory: dist/
echo You can now run: npm run preview
echo Or deploy the dist/ folder to any static hosting
echo ========================================
pause