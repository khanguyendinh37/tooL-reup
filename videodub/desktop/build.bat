@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo   VideoDub - Desktop Build (Windows)
echo ========================================
echo.

set "ROOT=%~dp0.."
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"
set "DESKTOP=%ROOT%\desktop"
set "VENV=%BACKEND%\.venv"
set "VPY=%VENV%\Scripts\python.exe"
set "FFMPEG_DIR=%DESKTOP%\vendor\ffmpeg"

where.exe node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js khong co trong PATH.
    exit /b 1
)

if not exist "%VPY%" (
    echo [1/6] Tao backend virtualenv...
    rem Prefer the Python 3.11 interpreter installed by setup-python.
    set "PY_BIN=py -3.11"
    python -c "import sys; sys.exit(sys.version_info[:2] != (3, 11))" >nul 2>&1
    if not errorlevel 1 set "PY_BIN=python"
    !PY_BIN! -m venv "%VENV%"
    if errorlevel 1 (
        echo [ERROR] Khong tao duoc Python 3.11 virtualenv.
        echo         Cai Python 3.11 tu https://www.python.org/downloads/ roi chay lai.
        exit /b 1
    )
) else (
    echo [1/6] Tai su dung backend virtualenv.
)

if not exist "%FRONTEND%\node_modules" (
    echo [2/6] Cai frontend dependencies...
    pushd "%FRONTEND%"
    call npm ci
    if errorlevel 1 (
        popd
        echo [ERROR] npm ci that bai.
        exit /b 1
    )
    popd
) else (
    echo [2/6] Frontend dependencies da co.
)

echo [3/6] Build frontend production...
pushd "%FRONTEND%"
call npm run build
if errorlevel 1 (
    popd
    echo [ERROR] Frontend build that bai.
    exit /b 1
)
popd

echo [4/6] Cai dependencies desktop va backend...
"%VPY%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"%VPY%" -m pip install -r "%DESKTOP%\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Cai Python dependencies that bai.
    exit /b 1
)

if not exist "%FFMPEG_DIR%" mkdir "%FFMPEG_DIR%"

echo [5/7] Tao icon VideoDub...
"%VPY%" "%DESKTOP%\create_icon.py"
if errorlevel 1 (
    echo [ERROR] Khong tao duoc icon.
    exit /b 1
)

set "FFMPEG_SOURCE="
for /f "delims=" %%F in ('where.exe ffmpeg 2^>nul') do if not defined FFMPEG_SOURCE set "FFMPEG_SOURCE=%%F"
set "FFPROBE_SOURCE="
for /f "delims=" %%F in ('where.exe ffprobe 2^>nul') do if not defined FFPROBE_SOURCE set "FFPROBE_SOURCE=%%F"

if not defined FFMPEG_SOURCE (
    echo [ERROR] Khong tim thay ffmpeg.exe trong PATH.
    echo         Cai FFmpeg roi chay lai script.
    exit /b 1
)
if not defined FFPROBE_SOURCE (
    echo [ERROR] Khong tim thay ffprobe.exe trong PATH.
    echo         Cai FFmpeg roi chay lai script.
    exit /b 1
)

echo [6/7] Dong goi FFmpeg vao ban desktop...
copy /Y "!FFMPEG_SOURCE!" "%FFMPEG_DIR%\ffmpeg.exe" >nul
copy /Y "!FFPROBE_SOURCE!" "%FFMPEG_DIR%\ffprobe.exe" >nul
if errorlevel 1 (
    echo [ERROR] Khong copy duoc FFmpeg binaries.
    exit /b 1
)

echo [7/7] Build VideoDub.exe (onedir)...
pushd "%DESKTOP%"
"%VPY%" -m PyInstaller --noconfirm --clean --distpath "%DESKTOP%\dist" --workpath "%DESKTOP%\build" VideoDub.spec
if errorlevel 1 (
    popd
    echo [ERROR] PyInstaller build that bai.
    exit /b 1
)
popd

if not exist "%DESKTOP%\dist\VideoDub\VideoDub.exe" (
    echo [ERROR] PyInstaller khong tao VideoDub.exe tai thu muc dist.
    exit /b 1
)

echo.
echo ========================================
echo   Desktop build completed!
echo ========================================
echo.
echo App folder:
echo   %DESKTOP%\dist\VideoDub
echo.
echo Run:
echo   desktop\run_desktop.bat
if not defined CI pause
endlocal
exit /b 0
