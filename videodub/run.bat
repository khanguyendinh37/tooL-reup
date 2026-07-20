@echo off
echo ===================================
echo   VideoDub - Tool Long Tieng Video
echo ===================================
echo.

echo [1/3] Kiem tra va cai dat Python dependencies...
cd backend
pip install --upgrade pip
pip install -r requirements.txt
cd ..

echo [2/3] Khoi dong Backend (FastAPI)...
start "VideoDub Backend" cmd /k "cd backend && python -m uvicorn app.main:app --reload --port 8000"

timeout /t 3 /nobreak >nul

echo [3/3] Khoi dong Frontend (React)...
start "VideoDub Frontend" cmd /k "cd frontend && npm install && npm run dev"

echo.
echo ===================================
echo   VideoDub dang chay!
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000
echo ===================================
pause
