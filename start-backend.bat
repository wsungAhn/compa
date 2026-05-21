@echo off
echo DB 준비 대기 중...
:wait_db
wsl -e bash -c "docker exec $(docker ps -qf name=compa-db) pg_isready -U compa" >nul 2>&1
if errorlevel 1 (
    echo   아직 준비 중...
    timeout /t 2 /nobreak >nul
    goto wait_db
)
echo DB 준비 완료!
wsl -e bash -c "cd /home/compa/compa/backend && .venv/bin/uvicorn app.main:app --reload --port 8000"
pause
