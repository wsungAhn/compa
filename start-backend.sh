#!/bin/bash
echo "DB 준비 대기 중..."
for i in $(seq 1 20); do
    if docker exec $(docker ps -qf "name=compa-db-1") pg_isready -U compa 2>/dev/null; then
        echo "DB 준비 완료!"
        break
    fi
    echo "  대기 중... ($i/20)"
    sleep 2
done

cd /home/compa/compa/backend
.venv/bin/uvicorn app.main:app --reload --port 8000
echo ""
echo "서버가 종료됐습니다. Enter를 누르면 창이 닫힙니다."
read -r
