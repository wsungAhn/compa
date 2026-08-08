# Cowork Conventions — compa

## Handoff location & naming
- **Folder:** `cowork/`
- **Filename:** `YYYY-MM-DD-handoff.md` (suffix `-2`, `-<topic>` if multiple per day)
- **Template:** cowork-handoff skill의 `assets/handoff-template.md`

## Executor
- **Default executor:** Codex CLI (`codex`)

## Execution environment
- **Interpreter (backend):** `backend/.venv/bin/python` (Python 3.11.8)
- **Interpreter (frontend):** Node (npm) — `frontend/`
- **Test command (backend):** `cd backend && .venv/bin/python -m pytest tests/ -q`
- **Type check (backend):** `cd backend && .venv/bin/python -m mypy --strict app/`
- **Build/lint (frontend):** `cd frontend && npm run build && npm run lint`
- **Current test baseline (2026-08-08 재실측):**
  - backend: `484 passed, 1 skipped` (1.71s)
  - 그 1 skipped는 상시 스킵이다: `tests/scrapers/test_amoremall.py:160`
    ("실제 Playwright/네트워크 호출 — CI에서 스킵"). 건드리지 말 것
  - ⚠️ **이 484는 로컬(PostgreSQL 가동 중) 수치다.** live PG에 의존하면서 skip 가드가
    없는 테스트가 4개 있고(`test_sale_windows`/`test_match_products`/`test_feedback`/
    `test_admin`) `.github/workflows/ci.yml`엔 postgres 서비스가 없다 — CI backend 잡은
    현재 녹색일 수 없다(선재 결함, 2026-08-08 감사에서 발견)
  - 워크트리에는 `.venv`가 없다. main의 venv를 쓰되 cwd는 워크트리로:
    `PYTHONPATH=. /Users/Mung/dev/compa/backend/.venv/bin/python -m pytest tests/ -q`
- **(구) 2026-07-15 베이스라인:** `327 passed, 1 skipped`
  - mypy --strict: `Success: no issues found in 74 source files`
  - frontend: build 성공(vite chunk-size 경고만) + lint 통과 + `npm run test` 9 passed
  - npm audit: `found 0 vulnerabilities`
- **프로젝트 경로:** `/Users/Mung/dev/compa`
- Playwright는 `executable_path="/usr/bin/google-chrome-stable"` — 이 Mac에는 없을 수 있음,
  Playwright 관련 스크래퍼 변경 시 executor가 직접 실행 검증은 스킵하고 코드 정합성만 확인

## Coding rules (from CLAUDE.md)
- `.env` 커밋 금지 / API 키 하드코딩 금지
- `requests` 금지 → `httpx.AsyncClient` 사용
- async 라우트 안에서 동기 호출 금지 (블로킹 작업은 `asyncio.to_thread`)
- DB 스키마 직접 변경 금지 → Alembic 필수
- 스크래퍼는 반드시 `BaseScraper` 상속, rate limit 준수
- 에러 발생 시 `raw_text` 보존 + `confidence=0`, 예외 전파 금지
- 금액은 `NUMERIC(12,2)`, currency 컬럼 별도
- `mypy --strict` 통과 / TS `strict` 유지 / 테스트 없이 스크래퍼 머지 금지

## Guardrails
- live 결제/구독(premium) 코드 건드리지 않음 (이번 작업 범위 외)
- `.env` 파일 생성/수정 금지 (`.env.example`만)
- Executor는 커밋하지 않음 — working tree만 변경

## Commit & landing policy
- **커밋:** reviewer(Claude)가 직접 검증 후 커밋
- **접두사:** `feat:` `fix:` `refactor:` `chore:` `test:`
- **Restart (2026-08-08 정정 — 이전 기술 "상시 데몬 없음"은 틀렸다):**
  compa는 launchd로 **worker/beat/api 3개가 상시 가동 중**이다
  (`com.compa.worker` / `com.compa.beat` / `com.compa.api`).
  코드 변경은 재시작해야 반영된다 — `launchctl kickstart -k gui/$(id -u)/<label>`
- **⛔ 배포 경로 게이트 (2026-08-08 실측):** 세 서비스 모두 `WorkingDirectory`가
  `/Users/Mung/dev/compa/backend` = **main 체크아웃**이고 실행 바이너리도 main venv다.
  **워크트리에서 고치고 재시작해도 운영은 구코드를 계속 돈다.** 워크트리 작업은
  반드시 `main 머지 → 재시작` 순서를 거쳐야 반영된다. 관찰 전에 서비스 cwd/venv에서
  런타임 import로 실제 반영을 먼저 확인할 것:
  `cd /Users/Mung/dev/compa/backend && PYTHONPATH=. .venv/bin/python -c "from app.core import database; print(database.__file__, type(database.engine.pool).__name__)"`
