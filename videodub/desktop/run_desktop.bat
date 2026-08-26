@echo off
setlocal
set "ROOT=%~dp0.."
set "APP=%~dp0dist\VideoDub\VideoDub.exe"

if not exist "%APP%" (
    echo [ERROR] Chua co ban desktop da build.
    echo         Hay chay desktop\build.bat truoc.
    pause
    exit /b 1
)

start "VideoDub" "%APP%"
endlocal
