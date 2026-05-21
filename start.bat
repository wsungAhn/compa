@echo off
echo [1/4] Docker 데몬 시작...
wsl -e bash -c "sudo service docker start && sleep 2"

echo [2/4] DB + Redis 시작...
wsl -e bash -c "docker compose -f /mnt/d/dev/compa/docker-compose.yml --env-file /home/compa/compa/backend/.env up -d db redis"

echo [3/4] 백엔드 시작...
start "COMPA Backend" D:\dev\compa\start-backend.bat

echo [4/4] 프론트엔드 시작...
start "COMPA Frontend" D:\dev\compa\start-frontend.bat

echo 완료! http://localhost:5173
