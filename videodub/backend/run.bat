@echo off
setlocal EnableDelayedExpansion
echo ========================================
echo   VideoDub Backend - Development Server
echo ========================================
echo.

set "ROOT=%~dp0.."
set "VENV=%~dp0.venv"
set "VPY=%VENV%\Scripts\python.exe"
set "VPIP=%VENV%\Scripts\pip.exe"

if not defined VIDEODUB_DATA_DIR set "VIDEODUB_DATA_DIR=%LOCALAPPDATA%\VideoDub"
if not exist "%VIDEODUB_DATA_DIR%" mkdir "%VIDEODUB_DATA_DIR%"

REM Release the fixed dev ports first. A stale uvicorn - or the orphaned
REM children of a crashed one - otherwise keeps the port and swallows requests.
call "%ROOT%\stop-local.bat" /quiet

echo [1/2] Preparing backend virtualenv...
if not exist "%VPY%" (
    echo     Creating venv at "%VENV%" ...
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtualenv.
        pause
        exit /b 1
    )
) else (
    echo     venv already exists - reusing.
)

REM Idempotent dependency sync: reinstall only when requirements.txt changed.
set "MARKER=%VENV%\.deps_installed"
set "NEED_INSTALL=1"
if exist "%MARKER%" (
    for /f "delims=" %%H in ('certutil -hashfile "%~dp0requirements.txt" SHA1 ^| findstr /r "^[0-9a-f]"') do set "NEW_HASH=%%H"
    set /p OLD_HASH=<"%MARKER%"
    if "!NEW_HASH!"=="!OLD_HASH!" set "NEED_INSTALL=0"
)

echo [2/2] Syncing backend dependencies...
if "!NEED_INSTALL!"=="1" (
    echo     Installing requirements into venv...
    "%VPIP%" install --upgrade pip
    for /f "usebackq eol=# tokens=*" %%L in ("%~dp0requirements.txt") do (
        set "LINE=%%L"
        if not "!LINE!"=="" (
            "%VPIP%" install "!LINE!"
            if errorlevel 1 (
                echo [ERROR] Failed to install: !LINE!
                pause
                exit /b 1
            )
        )
    )
    for /f "delims=" %%H in ('certutil -hashfile "%~dp0requirements.txt" SHA1 ^| findstr /r "^[0-9a-f]"') do echo %%H> "%MARKER%"
    echo     Backend deps synced.
) else (
    echo     Backend deps already up to date - skipping.
)

echo.
echo Backend API: http://localhost:8000
echo API Docs:    http://localhost:8000/docs
echo Press Ctrl+C to stop the server
echo.
"%VPY%" -m uvicorn app.main:app --reload --port 8000
pause
endlocal
