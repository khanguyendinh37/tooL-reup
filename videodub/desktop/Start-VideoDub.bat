@echo off
setlocal
rem Only unblock this extracted VideoDub distribution, never other downloads.
if not exist "%~dp0VideoDub.exe" (
    echo [ERROR] Keep this file beside VideoDub.exe and the _internal folder.
    pause
    exit /b 1
)
set "VIDEODUB_LAUNCH_DIR=%~dp0"
powershell.exe -NoProfile -Command "$ErrorActionPreference = 'Stop'; Get-ChildItem -LiteralPath $env:VIDEODUB_LAUNCH_DIR -Recurse -File | Unblock-File"
if errorlevel 1 (
    echo [ERROR] Could not unblock VideoDub. Extract it to a folder you can write to.
    pause
    exit /b 1
)
start "" /D "%~dp0" "%~dp0VideoDub.exe"
endlocal
