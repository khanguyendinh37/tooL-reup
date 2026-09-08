@echo off
setlocal EnableDelayedExpansion
echo ========================================
echo   VideoDub - Local Development Runner
echo ========================================
echo.

REM ----------------------------------------
REM Preflight: check Python and Node
REM ----------------------------------------
call python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Install from https://python.org then re-run.
    pause
    exit /b 1
)
call node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found in PATH. Install from https://nodejs.org then re-run.
    pause
    exit /b 1
)

REM ----------------------------------------
REM [1/4] Bootstrap backend virtualenv
REM    Avoids "twisted cmd redirect" junk files (=X.Y.Z) caused by
REM    `pip install pkg>=version` when run in raw cmd. venv lets us
REM    install once with quoted specs and never re-download.
REM ----------------------------------------
set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
if exist "%ROOT%desktop\vendor\ffmpeg\ffmpeg.exe" set "PATH=%ROOT%desktop\vendor\ffmpeg;%PATH%"
set "VENV=%BACKEND%\.venv"

REM Use the same persistent settings as the desktop build unless overridden.
if not defined VIDEODUB_DATA_DIR set "VIDEODUB_DATA_DIR=%LOCALAPPDATA%\VideoDub"
if not exist "%VIDEODUB_DATA_DIR%" mkdir "%VIDEODUB_DATA_DIR%"

REM Stop stale VideoDub dev instances so the new source is served on the documented ports.
call "%ROOT%stop-local.bat" /quiet

echo [1/4] Preparing backend virtualenv...
if not exist "%VENV%\Scripts\python.exe" (
    echo     Creating venv at "%VENV%" ...
    pushd "%BACKEND%"
    call python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtualenv.
        popd
        pause
        exit /b 1
    )
    popd
) else (
    echo     venv already exists - reusing.
)

REM Use venv's pip/python for install
set "VPY=%VENV%\Scripts\python.exe"
set "VPIP=%VENV%\Scripts\pip.exe"
"%VPY%" -c "import sys; sys.exit(not (sys.version_info[:2] == (3, 11)))"
if errorlevel 1 (
    echo [ERROR] VideoDub requires Python 3.11, matching the desktop build.
    pause
    exit /b 1
)

REM ----------------------------------------
REM [2/4] Sync backend deps
REM    Idempotent: only (re)install when marker missing or requirements changed.
REM    Marker holds a hash of requirements.txt so we skip re-install when nothing changed.
REM ----------------------------------------
set "MARKER=%VENV%\.deps_installed"
set "NEED_INSTALL=1"
if exist "%MARKER%" (
    for /f "delims=" %%H in ('certutil -hashfile "%BACKEND%\requirements.txt" SHA1 ^| findstr /r "^[0-9a-f]"') do set "NEW_HASH=%%H"
    set /p OLD_HASH=<"%MARKER%"
    if "!NEW_HASH!"=="!OLD_HASH!" set "NEED_INSTALL=0"
)

echo [2/4] Syncing backend dependencies...
if "!NEED_INSTALL!"=="1" (
    echo     Installing requirements into venv...
    "%VPIP%" install --upgrade pip
    "%VPY%" -m pip install -r "%BACKEND%\requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Dependency sync failed.
        exit /b 1
    )
    "%VPY%" -m pip check
    if errorlevel 1 exit /b 1
    for /f "delims=" %%H in ('certutil -hashfile "%BACKEND%\requirements.txt" SHA1 ^| findstr /r "^[0-9a-f]"') do echo %%H> "%MARKER%"
    echo     Backend deps synced.
) else (
    echo     Backend deps already up to date - skipping.
)

REM ----------------------------------------
REM [3/4] Sync frontend deps
REM    Idempotent: npm ci only when node_modules missing or package-lock changed.
REM ----------------------------------------
set "FRONTEND=%ROOT%frontend"
set "FMARKER=%FRONTEND%\node_modules\.deps_installed"
set "FNEED_INSTALL=1"
if exist "%FRONTEND%\node_modules" (
    if exist "%FMARKER%" (
        for /f "delims=" %%H in ('certutil -hashfile "%FRONTEND%\package-lock.json" SHA1 ^| findstr /r "^[0-9a-f]"') do set "FNEW=%%H"
        set /p FOLD=<"%FMARKER%"
        if "!FNEW!"=="!FOLD!" set "FNEED_INSTALL=0"
    )
) else (
    echo     node_modules missing - will install.
)

echo [3/4] Syncing frontend dependencies...
if "!FNEED_INSTALL!"=="1" (
    pushd "%FRONTEND%"
    call npm ci
    if errorlevel 1 (
        echo [ERROR] npm ci failed.
        popd
        pause
        exit /b 1
    )
    for /f "delims=" %%H in ('certutil -hashfile "%FRONTEND%\package-lock.json" SHA1 ^| findstr /r "^[0-9a-f]"') do echo %%H> "%FMARKER%"
    popd
    echo     Frontend deps synced.
) else (
    echo     Frontend deps already up to date - skipping.
)

REM ----------------------------------------
REM [4/4] Launch dev servers
REM    Backend uses venv python. Frontend uses vite dev.
REM    Both run in their own window so you can see logs / stop with Ctrl+C.
REM ----------------------------------------
echo [4/4] Launching dev servers...
echo.
start "VideoDub Backend" /D "%BACKEND%" powershell.exe -NoProfile -NoExit -Command "& '%VPY%' -m uvicorn app.main:app --reload --port 8000"
powershell.exe -NoProfile -Command "Start-Sleep -Seconds 3"
start "VideoDub Frontend" /D "%FRONTEND%" "%ComSpec%" /k npm.cmd run dev -- --force --host 127.0.0.1 --port 5173 --strictPort

echo ========================================
echo   VideoDub is starting!
echo ========================================
echo.
echo Frontend:  http://localhost:5173
echo Backend:   http://localhost:8000
echo API Docs:  http://localhost:8000/docs
echo Health:    http://localhost:8000/api/health
echo.
echo Two console windows opened - close them to stop the servers.
echo ========================================
endlocal
pause
