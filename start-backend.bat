@echo off
title COMPA Backend (:8000)

echo [1/3] Killing existing process on port 8000...
wsl bash -c "fuser -k 8000/tcp 2>/dev/null; sleep 1; true"

echo [2/3] Waiting for DB...
:wait_db
wsl bash -c "docker ps -qf name=compa-db | xargs -r -I{} docker exec {} pg_isready -U compa -q 2>/dev/null" >nul 2>&1
if errorlevel 1 (
    echo   DB not ready yet...
    timeout /t 2 /nobreak >nul
    goto wait_db
)
echo DB is ready!

echo [3/3] Starting Uvicorn...
wsl bash -c "cd /home/compa/compa/backend && .venv/bin/uvicorn app.main:app --reload --port 8000"
echo.
echo [Backend stopped]
pause
