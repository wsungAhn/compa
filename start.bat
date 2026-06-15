@echo off
title COMPA Launcher

echo [1/5] Starting Docker daemon...
wsl bash -c "sudo service docker start 2>/dev/null; sleep 1"

echo [2/5] Starting DB + Redis...
wsl bash -c "docker compose -f /mnt/d/dev/compa/docker-compose.yml --env-file /home/compa/compa/backend/.env up -d db redis"
if errorlevel 1 (
    echo ERROR: DB/Redis failed to start. Check if Docker is running.
    pause
    exit /b 1
)

echo [3/5] Opening Backend window...
start "COMPA Backend" cmd /k "D:\dev\compa\start-backend.bat"

echo [4/5] Opening Celery window...
timeout /t 3 /nobreak >nul
start "COMPA Celery" cmd /k "D:\dev\compa\start-celery.bat"

echo [5/5] Opening Frontend window...
start "COMPA Frontend" cmd /k "D:\dev\compa\start-frontend.bat"

echo.
echo ================================================
echo  COMPA started. You can close this window.
echo  Frontend : http://localhost:5173
echo  API docs : http://localhost:8000/docs
echo ================================================
pause
