@echo off
setlocal

REM Release only listeners on VideoDub's fixed local development ports.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ports = @(8000,5173); $ids = Get-NetTCPConnection -LocalPort $ports -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; foreach ($id in $ids) { & taskkill.exe /PID $id /T /F 2>$null | Out-Null }"

if /I not "%~1"=="/quiet" (
    echo VideoDub local development ports 8000 and 5173 released.
    pause
)
endlocal
