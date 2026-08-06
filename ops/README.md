# 상주 운영 (macOS, Mac Studio)

기존 `start.sh`/`start.bat`은 WSL 전제(Docker·`/mnt/d` 경로)라 이 머신에서는 쓰지 않는다.

## 구성

| 프로세스 | LaunchAgent | 비고 |
|---|---|---|
| API + 프론트 | `com.compa.api` | uvicorn `127.0.0.1:8000`. FastAPI가 `frontend/dist`를 같은 오리진에서 서빙하므로 정적 서버가 따로 없다 |
| 수집 워커 | `com.compa.worker` | Celery worker (concurrency 2) |
| 스케줄러 | `com.compa.beat` | Celery beat — 일일 수집·분류·소셜 |

의존 서비스는 이미 상주 중이다: `homebrew.mxcl.postgresql@16`, `homebrew.mxcl.redis`,
`com.wsungahn.cloudflared-pm`(터널).

## 설치 / 재시작

```bash
cd ~/dev/compa/ops
for n in api worker beat; do
  cp com.compa.$n.plist ~/Library/LaunchAgents/
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.compa.$n.plist
done

# 코드 변경 후 반영 (파일만 고치면 떠 있는 프로세스는 구코드를 물고 돈다)
launchctl kickstart -k gui/$(id -u)/com.compa.api
launchctl kickstart -k gui/$(id -u)/com.compa.worker
launchctl kickstart -k gui/$(id -u)/com.compa.beat
```

로그: `ops/logs/{api,worker,beat}.{log,err.log}`

## 공개 주소

`https://compa.mwco.io` → Cloudflare Tunnel → `localhost:8000`.
터널 설정은 `~/.cloudflared/config.yml`(pm.mwco.io와 공유). 이전에는 Vite 개발서버
(5173)를 가리켜, 개발서버가 없으면 502였다.

프론트를 고치면 `cd frontend && npm run build` 후 API 재시작 없이 즉시 반영된다
(dist를 직접 서빙).
