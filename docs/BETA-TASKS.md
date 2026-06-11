# 베타 배포 준비 작업 명세 (코덱스 위임용)

> 목적: 완성된 기능을 외부 베타 테스터에게 웹앱으로 공개하기 전 필수 준비 작업.
> 작업 순서: T1 → T2 → T3 → **T4(공홈 스크래퍼, 우선)** → T5(콜드스타트 워밍업).
> T1·T2는 독립적이라 병렬 가능, T3는 마이그레이션 포함. T5는 T2·T4 완료 후 실행해야 의미가 있다.
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

## T4. 화장품 공홈(브랜드 공식몰) 스크래퍼 — 우선 과제

**문제**: 현재 수집원은 전부 리테일 플랫폼(올리브영·쿠팡 등)과 소셜이다.
브랜드 공식몰의 **자사몰 단독 세일**(멤버스 위크, 공식몰 단독 특가 등)이 전혀 잡히지 않는다.

**전략**: 브랜드별 스크래퍼 난립 대신 ① 설정 주도 프레임워크 + ② 최대 레버리지 사이트 1곳(아모레몰) 구현.
아모레몰(amoremall.com)은 설화수·라네즈·헤라·이니스프리·에뛰드·마몽드 등 아모레퍼시픽 계열
30여 개 브랜드의 공식 세일이 한 사이트에 모여 있어 단일 구현으로 커버리지가 가장 크다.

### 4-1. 공홈 스크래퍼 프레임워크

`backend/app/scrapers/kr/brand_base.py` (새 파일):
- `@dataclass class BrandSiteConfig`: platform_name, search_url_template, 셀렉터 묶음
  (item / name / brand / sale_price / original_price / promo_badge), currency, uses_playwright: bool.
- `class ConfigDrivenBrandScraper(BaseScraper)`: config를 받아 동작하는 공용 구현.
  - `uses_playwright=True`면 기존 oliveyoung.py의 Playwright 패턴(프록시 포함), 아니면 httpx+BS4 패턴.
  - 파싱은 순수 함수 `parse_brand_html(html: str, config: BrandSiteConfig, url: str) -> list[ScrapedEvent]`로 분리 (픽스처 테스트 대상).
  - 셀렉터는 각 항목당 다중 후보(쉼표 구분) 허용 — 기존 ulta.py의 방어적 패턴 준수.
  - 실패 시 confidence=0 + raw_text 보존, 예외 전파 금지.

→ 이후 브랜드 추가 = config 등록 + 픽스처 테스트 1개. 코드 수정 최소화.

### 4-2. 아모레몰 구현 (1호)

`backend/app/scrapers/kr/amoremall.py`:
- `AmoremallScraper` — PLATFORM_NAME "아모레몰", COUNTRY "KR", RATE_LIMIT_SEC 2.0,
  `uses_playwright=True` (SPA — JS 렌더링 필요. `domcontentloaded` + 2~3초 대기 후 파싱).
- 검색: `https://www.amoremall.com/kr/ko/search?query={query}` (배포 후 실페이지 기준으로
  셀렉터 보정 필요 — 명세의 셀렉터는 초안이며 다중 후보로 방어).
- 상품 카드에서 정가/할인가/할인율 추출 + **세일 배지·프로모션 문구**(예: "단독", "멤버스")가 있으면
  `reason`에 보존 → 분류기의 돌발 키워드("단독", "앱전용")와 연동된다.
- 기획전/이벤트 페이지(`/kr/ko/display/event` 류)가 접근 가능하면 oliveyoung.py의
  `_scrape_sale_events` 패턴으로 행사명+기간 수집 (start/end date 파싱, confidence 0.6).

### 4-3. 등록·설정

- `backend/app/core/seed.py` PLATFORMS에 추가:
  `{"name": "아모레몰", "country": "KR", "url": "https://www.amoremall.com", "scrape_method": "scraping"}`
- `collector.py` SCRAPERS에 `"아모레몰": AmoremallScraper` 등록.
- T2의 `ENABLED_SCRAPERS` 기본값에 "아모레몰" 포함:
  `ENABLED_SCRAPERS=네이버쇼핑,Rakuten,아모레몰`
- `.env.example` 갱신.

### 4-4. 테스트

`backend/tests/scrapers/test_amoremall.py` + `test_brand_base.py`:
- parse_brand_html 픽스처 테스트 (할인 상품 / 정가만 / 빈 HTML / 셀렉터 폴백 동작)
- 프로모션 문구 → reason 보존 검증
- config 다중 셀렉터 폴백 단위 테스트

**수용 기준**: 공통 검증 기준 + 위 테스트. 라이브 검증은 배포 후 실페이지에서 진행
(셀렉터가 틀려도 zero-confidence + raw_text로 남아 디버깅 가능해야 함 — 이게 합격 조건).

**후속 확장 (이번 범위 외)**: LG생활건강 계열·클리오·미샤 등은 T3의 search_logs로
베타 유저가 많이 찾는 브랜드 상위부터 config 추가. 해외 공홈(sulwhasoo.com/us 등)은 그 다음.

---

## T5. 콜드스타트 워밍업 배치 (T2·T4 완료 후 실행)

**문제**: products/sale_events 테이블이 비어 있어, 베타 오픈 직후 유저는 이력 없는
현재가 스냅샷만 보게 된다. 오픈 전에 인기 제품을 미리 수집해둬야 한다.

**변경 사항**:

1. `backend/app/data/seed_queries_kr.txt` (새 파일): 인기 화장품 검색어 100~200개,
   한 줄에 하나. 구성 가이드 — 스킨케어/메이크업/선케어/클렌징 균형, 브랜드+제품명 형태
   (예: "설화수 윤조에센스", "라네즈 워터뱅크 크림", "헤라 블랙쿠션", "코스알엑스 스네일 에센스",
   "넘버즈인 세럼", "토리든 다이브인 세럼" 등). 올리브영 어워즈·네이버 뷰티 랭킹 기준으로 선정.
2. `backend/app/tasks/warmup.py`: Celery task `warmup_collect(start_index: int = 0) -> int`
   — 파일을 읽어 각 검색어로 `collect_on_demand(db, query, force=False)` 순차 실행.
   - **beat 등록 금지** (1회성 수동 실행: `celery -A app.tasks call app.tasks.warmup.warmup_collect`)
   - 이미 수집된 쿼리는 `_is_fresh` 캐시로 자동 스킵 → 중단 후 재실행해도 안전(멱등).
   - 쿼리당 try/except continue, 진행 로그(logging) 출력, 처리 건수 반환.
   - `start_index`로 중단 지점부터 재개 가능.
3. include에 `app.tasks.warmup` 등록 (`app/tasks/__init__.py`).

**수용 기준**: 공통 검증 기준 + 파일 로더·인덱스 재개 로직 단위 테스트.
실행 시점: 배포 환경에서 T2 토글로 활성 스크래퍼 확정 후 1회 실행, 이후 Celery 일일
수집(`collect-all-daily`)이 자동으로 이력을 쌓는다.

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
