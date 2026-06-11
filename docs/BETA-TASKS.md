# 베타 배포 준비 작업 명세 (코덱스 위임용)

> 목적: 완성된 기능을 외부 베타 테스터에게 웹앱으로 공개하기 전 필수 준비 작업.
> 작업 순서: T1 → T2 → T3 (T1·T2는 독립적이라 병렬 가능, T3는 마이그레이션 포함이라 마지막 권장).
> 모든 작업은 CLAUDE.md 규칙을 따른다: 타입 힌트 필수(`mypy --strict` 통과), async I/O, `requests` 금지,
> 환경변수는 `core/config.py`의 `Settings`로만 접근, 스키마 변경은 반드시 Alembic migration.

## 공통 검증 기준 (모든 작업 완료 시)

```bash
cd backend && python -m pytest tests/ -q        # 전부 통과 (현재 280건)
cd backend && python -m mypy --strict app/      # 0 errors
cd frontend && npm run build && npm run lint    # strict 빌드 + lint 통과
```

---

## T1. CORS 도메인 설정 환경변수화

**문제**: `backend/app/main.py:24`에 `allow_origins=["http://localhost:5173"]` 하드코딩.
실 도메인으로 배포하면 프론트가 API를 호출할 수 없다.

**변경 사항**:

1. `backend/app/core/config.py` — `Settings`에 추가:
   ```python
   cors_origins: str = "http://localhost:5173"   # 쉼표 구분 목록
   ```
2. `backend/app/main.py` — `allow_origins=settings.cors_origins.split(",")` 로 교체
   (각 항목 `.strip()` 처리, 빈 문자열 제거).
3. `.env.example`에 추가:
   ```
   CORS_ORIGINS=http://localhost:5173,https://yourdomain.com
   ```

**수용 기준**: 기본값으로 기존 로컬 개발 동작 유지. env 설정 시 다중 도메인 허용.
파싱 로직(쉼표·공백 처리)을 순수 함수로 분리해 단위 테스트 2~3건 추가.

---

## T2. 스크래퍼 활성화 토글 (베타 안전 모드)

**문제**: `backend/app/scrapers/collector.py`의 `SCRAPERS` dict에 등록된 10개 스크래퍼가
검색 시 전부 실행된다. 쿠팡·Tmall·샤오홍슈·Amazon(HTML 폴백) 등은 실서버 IP에서
봇 차단 가능성이 높고, 차단당하면 응답 지연·IP 평판 하락만 남는다.
베타 초기에는 **공식 API 기반(네이버쇼핑·Rakuten)만 켜고** 나머지는 점진 활성화한다.

**변경 사항**:

1. `backend/app/core/config.py` — `Settings`에 추가:
   ```python
   enabled_scrapers: str = "네이버쇼핑,Rakuten"   # 쉼표 구분 플랫폼명, "all"이면 전체
   ```
2. `backend/app/scrapers/collector.py` — 순수 함수 추가:
   ```python
   def get_enabled_scrapers() -> dict[str, Callable[[], BaseScraper]]:
       # settings.enabled_scrapers 파싱: "all" → SCRAPERS 전체, 아니면 이름 매칭 부분집합
   ```
   `collect_on_demand`의 `SCRAPERS.items()` 순회를 `get_enabled_scrapers().items()`로 교체.
   존재하지 않는 이름은 무시(예외 금지). 이름 매칭은 SCRAPERS 키와 정확히 일치 기준.
3. `.env.example`에 추가:
   ```
   ENABLED_SCRAPERS=네이버쇼핑,Rakuten
   ```
4. `backend/app/main.py`의 `/health` 응답에 `"enabled_scrapers": [...]` 추가 (배포 후 설정 확인용).

**수용 기준**: 기본값에서 네이버쇼핑·Rakuten만 반환, `"all"` 시 전체,
잘못된 이름 포함 시 해당 항목만 무시. 단위 테스트 4건 이상 (monkeypatch로 settings 변경).
주의: 소셜 수집기(`app/social/`)는 API 키 부재 시 이미 빈 결과를 반환하므로 이번 범위에서 제외.

---

## T3. 피드백 채널 + 검색어 로깅

**목적**: 베타에서 가장 귀한 데이터 두 가지를 수집한다 —
(a) 사용자가 직접 남기는 피드백, (b) 무엇을 검색하는지.

### 3-1. DB 모델 + Alembic migration

`backend/app/models/feedback.py`:
```
feedbacks
- id UUID PK (uuid4)
- message TEXT NOT NULL          (최대 2000자, API에서 검증)
- contact VARCHAR(255) NULL      (선택 입력 — 이메일 등)
- page VARCHAR(100) NULL         (어느 화면에서 보냈는지)
- created_at TIMESTAMPTZ DEFAULT NOW()
```

`backend/app/models/search_log.py`:
```
search_logs
- id UUID PK (uuid4)
- query VARCHAR(255) NOT NULL
- lang VARCHAR(2) NOT NULL
- results_count INTEGER NOT NULL
- collecting BOOLEAN NOT NULL DEFAULT FALSE
- created_at TIMESTAMPTZ DEFAULT NOW()
- 인덱스: created_at
```

`backend/app/models/__init__.py`에 등록 후 **Alembic 자동생성 마이그레이션**:
`alembic revision --autogenerate -m "feedback and search_logs"` (직접 ALTER 금지).
CLAUDE.md 규칙대로 PK UUID·created_at 필수 준수.

### 3-2. API

`backend/app/api/feedback.py` (새 라우터, main.py에 등록):
- `POST /api/feedback` — body `{message: str, contact?: str, page?: str}`.
  Pydantic 검증: message 1~2000자, contact ≤255자. 성공 시 `{"ok": true}`.
  과도 호출 방지: 동일 프로세스 내 IP당 분당 5회 초과 시 429 (인메모리 dict로 충분, 외부 의존성 추가 금지).
- `GET /api/admin/feedback?token=...` — `Settings.admin_token: str = ""` 추가,
  토큰 불일치/미설정 시 404. 최근 100건 반환 (베타 운영용 간이 조회).

검색 로깅 — `backend/app/api/products.py`의 `search_products`:
- 응답 직전 `SearchLog` insert. **응답 지연 금지**: `background_tasks.add_task`로
  자체 세션(`AsyncSessionLocal`) 열어 insert (기존 `_collect_in_background` 패턴 재사용).
- 로깅 실패는 swallow (검색 기능에 영향 금지).
- PII 주의: query 외에 IP·UA 등 저장하지 않는다.

### 3-3. 프론트엔드

- `frontend/src/components/FeedbackButton.tsx` (새 파일):
  헤더 우측(SiteManager 옆)에 말풍선 아이콘 버튼 → 클릭 시 모달
  (textarea + 선택 이메일 입력 + 전송 버튼). 기존 카드 스타일(Tailwind, rounded-2xl) 준수.
  전송 성공 시 "고마워요! 더 나은 COMPA가 될게요 💌" 토스트 후 자동 닫힘. 실패 시 인라인 에러.
- `frontend/src/api/client.ts`에 `postFeedback(message, contact?, page?)` 추가.
- `App.tsx` 헤더에 버튼 배치. `strict` 유지, `any` 금지.

**수용 기준**: 마이그레이션 파일 생성 확인, feedback API 검증·rate-limit 테스트
(httpx AsyncClient + FastAPI TestClient 또는 스키마 단위 테스트), search 로깅이
실패해도 검색이 정상 동작하는 테스트, 프론트 빌드·lint 통과.

---

## 참고: 배포 구성 (이번 작업 범위 외 — 별도 진행)

도메인은 확보된 상태. 가장 단순한 권장 구성 (운영 지식 최소화):

1. **VPS 1대** (Hetzner CX22 ≈ €4/월 또는 AWS Lightsail $10/월, 2GB RAM 이상 — Playwright 때문에 4GB 권장)
2. 도메인 DNS A 레코드 → VPS IP
3. VPS에서 `docker compose up -d` (db·redis·api·worker·beat 전부 포함)
4. **Caddy** 컨테이너 추가: 리버스 프록시 + HTTPS 자동 발급(Let's Encrypt) + 프론트 빌드(`frontend/dist`) 정적 서빙.
   같은 도메인에서 `/api/*` → api:8000, 나머지 → 정적 파일. **same-origin이라 CORS 문제도 자연 해소**
   (T1은 그래도 수행 — 로컬 개발·향후 분리 대비).
5. `.env`에 실키 설정: `NAVER_CLIENT_ID/SECRET`(developers.naver.com에서 즉시 발급, 무료),
   `RAKUTEN_APP_ID`(webservice.rakuten.co.jp, 무료), `ANTHROPIC_API_KEY`, `ADMIN_TOKEN`, `CORS_ORIGINS`.

이 단계가 필요해지면 docker-compose에 Caddy 서비스 + Caddyfile 추가 작업을 별도 명세로 위임할 것.
