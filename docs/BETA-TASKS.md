# 베타 배포 준비 작업 명세 (코덱스 위임용)

> 목적: 완성된 기능을 외부 베타 테스터에게 웹앱으로 공개하기 전 필수 준비 작업.
> 작업 순서: T1 → T2 → T3 → T4(공홈) → T5(콜드스타트).
> **2026-06-12 갱신**: codex(master)와 claude 브랜치 통합 머지 반영. 피드백 5건에 대한 결정 확정(아래).
> 모든 작업은 CLAUDE.md 규칙을 따른다: `mypy --strict` 통과, async I/O, `requests` 금지,
> 환경변수는 `core/config.py`의 `Settings`로만 접근, 스키마 변경은 반드시 Alembic migration.

## 공통 검증 기준 (모든 작업 완료 시)

```bash
cd backend && python -m pytest tests/ -q        # 전부 통과
cd backend && python -m mypy --strict app/      # 0 errors
cd frontend && npm run build && npm run lint    # strict 빌드 + lint 통과
```

---

## 피드백 결정 사항 (2026-06-12 확정)

codex가 제기한 5개 결정 항목에 대한 최종 결정. **이 결정이 아래 T1~T5 명세에 이미 반영되어 있다.**

### #1 CORS 설정 — ✅ Option A 채택 (codex 권고 동의)
`Settings.allowed_origins: list[str]` + validator 유지. 브랜치 통합 머지에서 이미 반영 완료
(`main.py`가 `settings.allowed_origins` 사용). **T1은 `.env.example` 갱신과 파서 테스트만 남음.**
`cors_origins` 별도 필드는 추가하지 않는다 — 중복 설정 혼란 방지.

### #2 SCRAPERS 구조 — ✅ Option A 채택 (codex 권고 동의)
`SCRAPERS: dict[str, tuple[type[BaseScraper], str]]` (클래스, 검색언어) 구조가 머지 후 표준.
T2의 `get_enabled_scrapers()`는 이 구조 그대로 부분집합을 반환하고,
`collect_fast`·`collect_on_demand` 모두 enabled 설정과 교집합으로 실행한다.

### #3 admin 인증 — ⚠️ Option B 채택 (codex 권고 A와 다른 결정)
기존 `admin_secret`를 재사용하고 `admin_token`은 추가하지 않는다.
**근거**: 머지된 코드에 `admin_secret`가 이미 존재하고 이를 쓰는 admin API는 아직 없어
호환성 부담이 0이다. 운영자 입장에서 admin 인증 환경변수가 2개 존재하는 비용(혼동·문서화)이
문서 원안과의 일치성보다 크다. feedback admin 조회는 `ADMIN_SECRET` 하나로 통일.

### #4 search_logs.lang — ⚠️ Option B 채택 (codex 권고 A와 다른 결정)
`lang VARCHAR(8) NULL`로 설계하고, 미확정 시 `"auto"`를 저장한다.
**근거**: search_logs는 신규 테이블이라 제약을 처음부터 넓게 잡는 비용이 0이다.
`"un"` 같은 가짜 ISO 코드는 향후 실제 언어 감지가 들어왔을 때 데이터 오염으로 남는다.
머지 후 검색 API는 `lang` 파라미터가 없고 자동 번역 기반이므로, 로깅은
"원문 그대로 + lang='auto'"로 시작하고 언어 감지 도입 시 갱신한다.

### #5 feedback rate limit — ✅ Option A 변형 채택
프로세스 로컬 제한을 수용하되, **인메모리 dict 자체 구현 대신 머지로 도입된
slowapi limiter를 재사용한다**: `@limiter.limit("5/minute")`. 코드 일관성이 높고
테스트·주석으로 "프로세스 로컬" 한계를 명시한다. (slowapi도 기본 인메모리 — 베타 범위에서 충분.
멀티 worker 운영 시 Redis storage 옵션으로 전환 가능하다는 점을 주석에 남길 것.)

---

## T1. CORS 도메인 설정 — 거의 완료

머지로 `allowed_origins` 환경변수화가 반영됨. 남은 작업:

1. `.env.example`에 추가: `ALLOWED_ORIGINS=http://localhost:5173,https://yourdomain.com`
2. validator의 쉼표·공백 파싱 단위 테스트 2~3건 (`tests/core/test_config.py`).

---

## T2. 스크래퍼 활성화 토글 (베타 안전 모드)

**문제**: 검색 시 SCRAPERS에 등록된 16개(리테일 10 + 공홈 6)가 전부 실행됨.
쿠팡·Tmall·샤오홍슈·Amazon(HTML 폴백)은 실서버 IP에서 차단 위험이 높다.

**변경 사항**:

1. `Settings.enabled_scrapers: str = "네이버쇼핑,Rakuten"` (쉼표 구분, `"all"`이면 전체).
2. `collector.py`에 `get_enabled_scrapers() -> dict[str, tuple[type[BaseScraper], str]]`:
   `"all"` → SCRAPERS 전체, 아니면 이름 정확 일치 부분집합, 미존재 이름은 무시(예외 금지).
   `collect_fast`와 `collect_on_demand`의 순회를 모두 이 함수 기반으로 교체.
3. `.env.example`에 `ENABLED_SCRAPERS=네이버쇼핑,Rakuten` 추가.
4. `/health` 응답에 `"enabled_scrapers": [...]` 추가.

**수용 기준**: 기본값에서 2개만 반환, `"all"` 전체, 오타 무시. monkeypatch 단위 테스트 4건+.
소셜 수집기는 API 키 부재 시 이미 빈 결과 — 이번 범위 제외.

---

## T3. 피드백 채널 + 검색어 로깅

### 3-1. DB 모델 + Alembic migration

`backend/app/models/feedback.py`:
```
feedbacks: id UUID PK · message TEXT NOT NULL(≤2000자는 API 검증) · contact VARCHAR(255) NULL
         · page VARCHAR(100) NULL · created_at TIMESTAMPTZ DEFAULT NOW()
```

`backend/app/models/search_log.py`  (피드백 #4 결정 반영):
```
search_logs: id UUID PK · query VARCHAR(255) NOT NULL · lang VARCHAR(8) NULL("auto" 기본)
           · results_count INTEGER NOT NULL · collecting BOOLEAN NOT NULL DEFAULT FALSE
           · created_at TIMESTAMPTZ DEFAULT NOW() · 인덱스: created_at
```

`models/__init__.py` 등록 후 `alembic revision --autogenerate -m "feedback and search_logs"`.
현재 마이그레이션 체인 head는 `c7d4e8f2a1b3`(pg_trgm) — 그 뒤에 연결.

### 3-2. API

`backend/app/api/feedback.py` (새 라우터, main.py 등록):
- `POST /api/feedback` — `{message: str, contact?: str, page?: str}`. message 1~2000자 검증.
  rate limit은 **`@limiter.limit("5/minute")`** (피드백 #5 결정 — `app.core.limiter` 재사용,
  엔드포인트에 `request: Request` 파라미터 필요). 성공 시 `{"ok": true}`.
- `GET /api/admin/feedback` — **기존 `ADMIN_SECRET` 재사용** (피드백 #3 결정).
  쿼리 파라미터 `secret`이 `settings.admin_secret`과 불일치하거나 미설정이면 404. 최근 100건.

검색 로깅 — `api/products.py`의 `search_products` 응답 직전 `background_tasks.add_task`로
자체 세션을 열어 SearchLog insert (`_collect_in_background` 패턴 재사용). lang은 `"auto"` 저장.
로깅 실패는 swallow — 검색 기능에 영향 금지. IP·UA 등 PII 저장 금지.

### 3-3. 프론트엔드

- `FeedbackButton.tsx`: 헤더(SiteManager 옆) 말풍선 버튼 → 모달(textarea + 선택 이메일).
  성공 토스트 후 닫힘, 실패 인라인 에러. 기존 카드 스타일 준수, strict·no-any.
- `client.ts`에 `postFeedback(message, contact?, page?)` 추가.

**수용 기준**: 마이그레이션 생성, 검증·rate-limit 테스트, 로깅 실패 무해성 테스트, 빌드·lint 통과.

---

## T4. 공홈(브랜드 공식몰) 스크래퍼 — 아모레몰 추가

**현황 갱신**: 머지로 럭셔리 공홈 5종(SK-II·Shiseido·La Mer KR·Chantecaille KR·La Prairie·Tatcha)과
firecrawl 인프라가 이미 들어왔다. **T4의 남은 핵심은 아모레몰**이다 — 설화수·라네즈·헤라·이니스프리 등
아모레퍼시픽 30여 브랜드의 공식 세일이 한 사이트에 모여 있어 단일 구현 레버리지가 가장 크다.

1. `backend/app/scrapers/brands/amoremall.py`: 기존 `brands/` 스크래퍼들의 패턴(firecrawl 또는
   Playwright — 기존 파일들을 먼저 읽고 동일 패턴 채택)으로 `AmoremallScraper` 구현.
   - 검색: `https://www.amoremall.com/kr/ko/search?query={query}` (SPA — JS 렌더링 필요)
   - 상품 카드: 정가/할인가/할인율 + 세일 배지·프로모션 문구("단독", "멤버스")를 `reason`에 보존
     → 분류기 돌발 키워드와 연동됨.
   - 파싱은 순수 함수로 분리, 픽스처 테스트. 실패 시 confidence=0 + raw_text (합격 조건).
2. `collector.py` SCRAPERS에 `"아모레몰": (AmoremallScraper, "ko")` 등록, `seed.py`에 플랫폼 추가.
3. 후속 확장(LG생건·클리오·미샤 등)은 T3 search_logs에서 수요 상위 브랜드부터.

---

## T5. 콜드스타트 워밍업 — 대부분 완료, 검증·보강만

**현황 갱신**: 머지로 `scrapers/catalog.py`(SEED_BRANDS 기반 시딩) +
`tasks/seed.py`의 `seed_catalog_task`가 들어왔고, **앱 기동 시 DB가 비어 있으면 자동 디스패치**된다.

남은 작업:
1. `catalog.py`의 시딩이 `ENABLED_SCRAPERS`(T2) 설정을 존중하는지 확인·정합화.
2. SEED_BRANDS에 베타 타깃(한국 인기 제품) 보강 — 브랜드 단위가 아닌 "브랜드+대표제품" 검색어
   리스트로 확장하면 첫 검색 적중률이 높아진다 (예: "설화수 윤조에센스", "토리든 다이브인 세럼").
3. 중단·재실행 멱등성 테스트 (이미 수집된 항목 스킵 확인).

---

## 참고: 배포 구성 (이번 작업 범위 외 — 별도 진행)

도메인은 확보된 상태. 가장 단순한 권장 구성:

1. **VPS 1대** (Hetzner CX22 ≈ €4/월 또는 AWS Lightsail $10/월 — Playwright 때문에 RAM 4GB 권장)
2. 도메인 DNS A 레코드 → VPS IP
3. VPS에서 `docker compose up -d` (db·redis·api·worker·beat 포함)
4. **Caddy** 컨테이너 추가: HTTPS 자동 발급 + `frontend/dist` 정적 서빙 + `/api/*` → api:8000
   리버스 프록시. same-origin이라 CORS 문제 자연 해소.
5. `.env` 실키: `NAVER_CLIENT_ID/SECRET`(무료 즉시 발급), `RAKUTEN_APP_ID`(무료),
   `ANTHROPIC_API_KEY`, `ADMIN_SECRET`, `ALLOWED_ORIGINS`, `ENABLED_SCRAPERS`.

이 단계가 필요해지면 Caddy 서비스 + Caddyfile 추가 작업을 별도 명세로 위임할 것.
