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
- **Current test baseline (2026-07-14 확인):**
  - backend: `310 passed, 1 skipped`
  - mypy --strict: `Success: no issues found in 73 source files`
  - frontend build: 성공 (vite chunk-size 경고만, 무시 가능)
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
- **Restart:** 이 프로젝트는 상시 데몬 없음(로컬 개발 서버는 수동 기동) — 랜딩 후 재시작 불필요
