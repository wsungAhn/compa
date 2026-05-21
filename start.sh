#!/bin/bash
# COMPA 개발 서버 시작 스크립트

echo "🐳 Docker (DB + Redis) 시작..."
cd /mnt/d/dev/compa && docker compose up -d db redis

echo "⏳ DB 준비 대기..."
sleep 3

echo "🚀 백엔드 서버 시작..."
cd /home/compa/compa/backend && .venv/bin/uvicorn app.main:app --reload --port 8000
