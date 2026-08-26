@echo off
setlocal

REM Release listeners on VideoDub's fixed local development ports. A crashed
REM "uvicorn --reload" can leave orphaned multiprocessing children holding the
REM inherited listening socket after their parent died; netstat then reports a
REM dead PID that taskkill cannot touch. So: kill the live port owners first,
REM and only if a port is still held, sweep stray app/uvicorn/spawn processes.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ports = @(8000,5173);" ^
    "$owners = Get-NetTCPConnection -LocalPort $ports -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique;" ^
    "foreach ($id in $owners) { if ($id -and (Get-Process -Id $id -ErrorAction SilentlyContinue)) { & taskkill.exe /PID $id /T /F 2>$null | Out-Null } };" ^
    "$held = Get-NetTCPConnection -LocalPort $ports -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique;" ^
    "if ($held) {" ^
    "$live = Get-Process -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id;" ^
    "$strays = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -and ($_.CommandLine -match 'app\.main:app' -or ($_.CommandLine -match 'spawn_main' -and $live -notcontains $_.ParentProcessId)) };" ^
    "foreach ($s in $strays) { & taskkill.exe /PID $s.ProcessId /T /F 2>$null | Out-Null }" ^
    "};" ^
    "Start-Sleep -Milliseconds 400;" ^
    "$left = Get-NetTCPConnection -LocalPort $ports -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique;" ^
    "if ($left) { Write-Output ('WARNING: ports 8000/5173 still held by live PIDs: ' + ($left -join ', ')) } else { Write-Output 'Ports 8000 and 5173 released.' }"

if /I not "%~1"=="/quiet" (
    pause
)
endlocal
