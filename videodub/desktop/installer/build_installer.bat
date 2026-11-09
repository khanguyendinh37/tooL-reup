@echo off
setlocal
REM Build the Windows installer from an existing desktop\dist\VideoDub folder.
REM Usage: installer\build_installer.bat [version]
REM Requires Inno Setup 6 (https://jrsoftware.org/isinfo.php or: winget install JRSoftware.InnoSetup).

set "HERE=%~dp0"
set "VERSION=%~1"
if "%VERSION%"=="" set "VERSION=1.0.0"

if not exist "%HERE%..\dist\VideoDub\VideoDub.exe" (
    echo [ERROR] Chua co desktop\dist\VideoDub\VideoDub.exe. Chay desktop\build.bat truoc.
    exit /b 1
)

set "ISCC="
for /f "delims=" %%F in ('where.exe ISCC.exe 2^>nul') do if not defined ISCC set "ISCC=%%F"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo [ERROR] Khong tim thay Inno Setup 6 ^(ISCC.exe^).
    echo         Cai bang: winget install JRSoftware.InnoSetup
    exit /b 1
)

if not exist "%HERE%MicrosoftEdgeWebview2Setup.exe" (
    echo Tai WebView2 bootstrapper...
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile '%HERE%MicrosoftEdgeWebview2Setup.exe'"
)

"%ISCC%" /Qp /DAppVersion=%VERSION% "%HERE%VideoDub.iss"
if errorlevel 1 (
    echo [ERROR] Build installer that bai.
    exit /b 1
)
echo.
echo Installer: %HERE%..\dist\installer\VideoDub-Setup-%VERSION%.exe
endlocal
