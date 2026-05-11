# COMPA — 화장품 할인 행사 추적기

제품명 하나 입력 → 한국·미국·일본·중국 4개국 3년치 할인 이력 조회 → "지금 살지 / 기다릴지" 자동 추천 서비스.
타깃: 기초·색조·기능성 화장품. 수익: 광고(무료) + 구독(프리미엄).

---

## Tech Stack

| 레이어 | 기술 |
|--------|------|
| Backend API | Python 3.12 · FastAPI · Pydantic v2 |
| Task Queue | Celery + Redis |
| Database | PostgreSQL 16 · SQLAlchemy 2 · Alembic |
| Scraping | Playwright · httpx · BeautifulSoup4 · pytrends |
| AI (비정형) | Claude API `claude-sonnet-4-6` (프롬프트 캐싱) |
| AI (정형) | Gemma 4 2B via Ollama (로컬) |
| Frontend | React 18 · TypeScript · Vite · Tailwind CSS · Recharts |
| Infra | Docker Compose · GitHub Actions |

---

## 디렉토리 구조

```
compa/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI 라우터 (products, events, admin)
│   │   ├── scrapers/
│   │   │   ├── base.py     # BaseScraper 추상 클래스
│   │   │   ├── kr/         # oliveyoung, coupang, naver_shop
│   │   │   ├── us/         # sephora, ulta, amazon_us
│   │   │   ├── jp/         # cosme, rakuten
│   │   │   └── cn/         # tmall, xiaohongshu
│   │   ├── social/         # instagram, tiktok, facebook, naver_blog
│   │   ├── ai/             # extractor, classifier, matcher
│   │   ├── models/         # SQLAlchemy 모델 (product, platform, sale_event, social_post)
│   │   ├── tasks/          # Celery tasks (collect, classify)
│   │   └── core/           # config, database, proxy
│   ├── alembic/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/     # SearchBar, PriceChart, EventTimeline, WaitBuyWidget
│       ├── pages/          # Home, ProductDetail
│       └── api/            # client.ts
├── plan-feedback/          # 플랜 피드백 페이지 (배포 완료)
├── docker-compose.yml
├── .env.example
└── CLAUDE.md
```

---

## 핵심 커맨드

```bash
# 전체 서비스 기동
docker compose up -d

# 백엔드 개발 서버 (Docker 없이)
cd backend && uvicorn app.main:app --reload --port 8000

# DB 마이그레이션
alembic upgrade head
alembic revision --autogenerate -m "설명"

# 테스트
pytest tests/ -q
pytest tests/scrapers/ -q      # 스크래퍼만
pytest tests/ai/ -q            # AI 파이프라인만

# 프론트엔드
cd frontend && npm run dev      # 개발
cd frontend && npm run build    # 빌드

# Celery 워커 (로컬 테스트)
celery -A app.tasks worker --loglevel=info
```

---

## Python 코딩 규칙

- **타입 힌트 필수** — 모든 함수 인자·반환값에 타입 표기. `mypy --strict` 통과 기준.
- **비동기 I/O** — DB, HTTP 모두 async. `requests` 라이브러리 사용 금지, `httpx.AsyncClient` 사용.
- **네이밍** — 변수·함수 `snake_case`, 클래스 `PascalCase`, 상수 `UPPER_SNAKE_CASE`.
- **금액** — DB 저장 시 `NUMERIC(12,2)`, currency 컬럼 별도 관리. 정수 연산 금지.
- **스크래퍼** — 반드시 `BaseScraper` 상속. Rate limit 1 req/sec per domain 준수.
- **에러 처리** — 파싱 실패 시 raw_text 보존 + `confidence=0` 설정, 예외 전파 금지.
- **환경변수** — `core/config.py`의 `Settings` 클래스(Pydantic BaseSettings)로만 접근. 하드코딩 금지.

## TypeScript 코딩 규칙

- `strict: true` 필수. `any` 타입 사용 금지 — 대신 `unknown` + 타입 가드.
- 인터페이스 이름 `PascalCase`, `I` 접두사 없음.
- API 응답 타입은 OpenAPI 스키마에서 자동 생성 (`npm run gen-types`).
- 컴포넌트 파일명 `PascalCase.tsx`, 훅 파일명 `use*.ts`.

---

## AI 파이프라인 규칙

- **모델 ID**: `claude-sonnet-4-6` (변경 시 여기서만 수정)
- **역할 분리**: Gemma → 쇼핑몰 정형 데이터 / Claude → 소셜 비정형 텍스트
- **프롬프트 캐싱**: 시스템 프롬프트 1024토큰 이상 시 반드시 캐싱 적용
- **신뢰도**: `confidence < 0.7` → `needs_review=True` 플래그, 데이터 삭제 금지
- **PII**: Claude API에 개인정보(이름, 이메일 등) 전송 금지

---

## 데이터베이스 규칙

- 모든 PK는 UUID (`uuid_generate_v4()`)
- 모든 테이블에 `created_at TIMESTAMPTZ DEFAULT NOW()` 필수
- 소프트 삭제: `deleted_at TIMESTAMPTZ NULL` 컬럼 사용
- 스키마 변경 시 **항상 Alembic migration** 생성 후 적용, 직접 ALTER 금지
- 인덱스: `product_id`, `platform_id`, `start_date` 에 필수

---

## 절대 하지 말 것

- `.env` 파일 커밋 금지
- API 키·시크릿 하드코딩 금지
- `requests` 라이브러리 사용 금지 (httpx 사용)
- async 라우트 안에서 동기 DB 호출 금지
- Alembic 없이 DB 스키마 직접 변경 금지
- 테스트 없이 스크래퍼 코드 머지 금지

---

## 개발 마일스톤 현황

- [x] M0 준비: 플랜 확정, 훅 설치, GitHub 초기화
- [ ] M0: 환경 세팅 (docker-compose, alembic, FastAPI 기본앱)
- [ ] M1: 한국 수집기 + AI 파이프라인
- [ ] M2: 프론트엔드
- [ ] M3: 미국·일본 확장
- [ ] M4: 중국·소셜 + 수익화
