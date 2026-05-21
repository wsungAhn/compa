# COMPA — 화장품 할인 추적기

제품명 입력 → 한·미·일·중 4개국 3년치 할인 이력 → "지금 살지 / 기다릴지" 추천.

---

## 핵심 커맨드

```bash
# 백엔드 (WSL)
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
cd backend && .venv/bin/alembic upgrade head
cd backend && .venv/bin/alembic revision --autogenerate -m "설명"

# 프론트엔드
cd frontend && npm run dev
```

---

## 스택

| 레이어 | 기술 |
|--------|------|
| Backend | Python 3.14 · FastAPI · SQLAlchemy 2 · Alembic |
| Scraping | Playwright (Google Chrome `/usr/bin/google-chrome-stable`) · httpx · deep-translator |
| AI | Claude `claude-sonnet-4-6` (프롬프트 캐싱) |
| Frontend | React 19 · TypeScript · Vite · Tailwind CSS v4 |
| DB | PostgreSQL 16 · Redis |

> Playwright는 반드시 `executable_path="/usr/bin/google-chrome-stable"`, `args=["--no-sandbox", "--disable-dev-shm-usage"]`

---

## 절대 규칙

- `.env` 커밋 금지 / API 키 하드코딩 금지
- `requests` 금지 → `httpx.AsyncClient` 사용
- async 라우트 안에서 동기 DB 호출 금지
- DB 스키마 직접 변경 금지 → Alembic 필수
- 스크래퍼는 반드시 `BaseScraper` 상속, rate limit 준수
- 에러 발생 시 `raw_text` 보존 + `confidence=0`, 예외 전파 금지
- 금액은 `NUMERIC(12,2)`, currency 컬럼 별도

---

## 에이전트 분업

5줄 이하 수정·설정 편집·핫픽스는 직접. 그 외는 반드시 서브에이전트 위임.

| 작업 | 담당 |
|------|------|
| 설계·리뷰·아키텍처 | 오케스트레이터 (sonnet) |
| 스크래퍼 코드·테스트 | `scraper` 에이전트 (haiku) |
| AI 파이프라인 코드 | `ai-pipeline` 에이전트 (haiku) |
| React 컴포넌트 | `frontend` 에이전트 (haiku) |

---

## 마일스톤

- [x] M0: 환경 세팅 (Docker, Alembic, FastAPI)
- [x] M1: 한국 수집기 + AI 파이프라인
- [x] M2: 프론트엔드
- [x] M3: 미국·일본 확장 (Sephora ✅, Rakuten ✅, Amazon ⚠️503)
- [ ] M4: 중국·소셜 + 수익화

---

## 메모리 관리

- 메모리 위치: `C:\Users\admin\.claude\projects\D--dev-compa\memory\`
- **컨텍스트 컴팩트 전에 반드시 메모리를 먼저 업데이트하고 컴팩트 진행**
- 새로운 기술 결정, API 변경, 미완료 태스크, 피드백이 생기면 즉시 저장
- 저장 유형: `project` (기술 결정·현재 상태) / `feedback` (협업 방식) / `user` (사용자 정보)

---

## 참조 문서

- **[docs/scrapers.md](docs/scrapers.md)** — 스크래퍼별 상태, 인증 방식, 차단 현황
- **[docs/api.md](docs/api.md)** — API 엔드포인트 명세
- **[docs/schema.md](docs/schema.md)** — DB 스키마 상세
- **[docs/known-issues.md](docs/known-issues.md)** — 알려진 기술 제약 및 해결 방향
