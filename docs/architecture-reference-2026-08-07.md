# Architecture Reference — COMPA (2026-08-07)

> `docs/PRD-2026-08-07.md`(WHAT/WHY)과 짝을 이루는 문서 — 이건 HOW다. 지금 실제로
> 존재하는 API·데이터모델·핵심 함수 시그니처를 그대로 옮긴 것. 새 프론트엔드나
> 새 기능을 설계할 때 "이미 있는 것"을 재발명하지 않도록 하는 게 목적.
>
> 2026-08-07 추가: §10(비주얼 레퍼런스)·§11(화면 인벤토리) — PRD+이 문서를 외부
> 디자인 도구에 넘길 때 기존 톤과 다른 결과가 나오지 않도록, 실제 컴포넌트에서
> 뽑은 색상·타이포·레이아웃 관례와 "새 화면이 몇 개 필요한가"를 명시했다.

## 1. 스택

| 레이어 | 기술 |
|---|---|
| Backend | Python 3.12+ · FastAPI · Pydantic v2 · SQLAlchemy 2(async) · Alembic |
| Task Queue | Celery + Redis (beat: 일일/시간별 자동화, §5 참고) |
| Scraping | Playwright · httpx · firecrawl(로컬 self-hosted) · deep-translator(레거시, C단계에서 로컬 모델로 대체 진행중) |
| AI | Claude(`claude-sonnet-4-6`, 프롬프트 캐싱) 또는 로컬 Ollama(`USE_LOCAL_AI=true`) — 번역 전용은 `translategemma:4b`로 분리 |
| Frontend | React 19 · TypeScript(strict) · Vite · Tailwind CSS v4 · Recharts. **라우팅 라이브러리 없음 — 단일 화면 SPA** |
| DB | PostgreSQL 16(pg_trgm) · Redis |

## 2. 디렉토리 구조

```
backend/app/
├── api/            products.py comparison.py jobs.py feedback.py admin.py
├── scrapers/       collector.py(레지스트리) + kr/ us/ jp/ cn/ brands/(Shopify 공홈) firecrawl_*
├── social/         instagram.py tiktok.py facebook.py naver_blog.py
├── ai/             matcher.py matching.py translator.py classifier.py extractor.py pipeline.py local_client.py
├── models/         product.py sale_event.py platform.py product_match_candidate.py sale_window.py social_post.py feedback.py search_log.py
├── tasks/          collect.py classify.py match_products.py social_collect.py social_extract.py reddit_signals.py seed.py
└── core/           config.py database.py fx.py premium.py affiliate.py size.py limiter.py url_safety.py

frontend/src/
├── App.tsx                     — 유일한 화면 조립부(라우팅 없음)
├── components/                 SearchBar WaitBuyWidget PriceComparison PriceChart
│                                EventTimeline SiteEventsGrid SiteTimeline SiteManager
│                                PremiumBanner AdSlot FeedbackButton EventCard
├── hooks/usePremium.ts
└── api/client.ts                axios 클라이언트 + 타입(ComparisonOut 등)
```

## 3. DB 스키마 (전체 모델)

### Product (`products`)
`id, name_kr, name_en, name_jp, name_cn, brand, category(base/color/functional), created_at, deleted_at`
파셜 유니크 인덱스 2개(2026-08-06 배포): `(lower(name_en), lower(brand))` WHERE `deleted_at IS NULL AND name_en IS NOT NULL`, 동일 패턴이 `name_jp`에도. **국가별 이름 4개를 한 행에 담는 게 크로스 통화 매칭의 전제** — 매칭이 안 되면 나라마다 별도 행(고아)이 생긴다.

### SaleEvent (`sale_events`)
`id, product_id(FK), platform_id(FK, NOT NULL), event_name, event_type(regular/surprise), start_date, end_date, original_price, sale_price(NUMERIC 12,2), discount_rate, currency(3자), reason, source_url, confidence, needs_review(bool), scraped_name, size_ml(Float), is_bundle, raw_text, created_at, deleted_at`
유니크 제약 `uq_sale_events_dedup`: `(product_id, platform_id, COALESCE(start_date), COALESCE(event_name,''), COALESCE(size_ml,-1))` — 같은 상품·플랫폼·용량 조합은 이벤트당 1행.

### Platform (`platforms`)
`id, name, country(2자), url, scrape_method(scraping/official_api/unofficial_api), created_at`

### ProductMatchCandidate (`product_match_candidates`, 2026-08-06 신규)
`id, orphan_product_id(FK), canonical_product_id(FK), score(Float), status(pending/approved/rejected), created_at, decided_at, decided_by`. 유니크: `orphan_product_id` 단독(오브 하나에 후보 하나).

### SaleWindow (`sale_windows`)
`id, iso_year, iso_week, brand, event_name, discount_pct, price, currency, scope, retailer, country, product_id, source, is_estimate, verified, sample_size, corroborations, confidence, recurrence_key`. 세일 시기를 ISO 주차 슬롯에 실측으로 쌓는 테이블 — 연도 간 조인으로 "다음 세일 언제" 예측에 쓰인다.

### SocialPost (`social_posts`)
`id, platform, post_url, content, posted_at, processed, failed, retry_count, last_error, sale_event_id(FK)`

### Feedback / SearchLog
`Feedback: message, contact, page, created_at` / `SearchLog: query, lang, results_count, collecting`

## 4. API 엔드포인트 (전체)

| 메서드 | 경로 | 인증 | 설명 |
|---|---|---|---|
| GET | `/api/products/search` | 없음 | DB 트라이그램 검색, 부족하면 `collect=true`로 백그라운드 수집 트리거 |
| GET | `/api/products/{id}/events` | premium 게이트 있음(일부 필드) | 3년 이력 + 추천, `premium_dep`로 프리미엄 여부에 따라 응답 제한 |
| GET | `/api/products/{id}/comparison` | 없음 | `preferred`(선호 플랫폼) 대비 `alternatives` 가격, `currency` 지정 시 전체 환산, `cheapest_platform`/`cheapest_saving_pct` 포함 — **크로스 통화 비교가 이미 이 응답에 실려 있다**(§PRD 7-4) |
| GET | `/api/jobs/{task_id}` | 없음 | Celery 작업 상태 폴링(수집 진행률용) |
| POST | `/api/feedback` | 없음(5/min rate limit) | 익명 피드백 저장 |
| GET | `/api/admin/feedback` | `X-Admin-Secret` 헤더 | 최근 피드백 100건 |
| GET | `/api/admin/product-matches` | `X-Admin-Secret` 헤더 | 매칭 후보 목록(`?status=pending` 등) |
| POST | `/api/admin/product-matches/{id}/approve` | `X-Admin-Secret` | 원자적 승인 + 즉시 병합(중복 승인은 409) |
| POST | `/api/admin/product-matches/{id}/reject` | `X-Admin-Secret` | 원자적 거부(중복은 409) |

**세일 예측은 이미 노출된다** — `core/sale_calendar.py:next_sale()`이 `products.py:209`
(`_build_recommendation`)에서 직접 호출돼 `/api/products/{id}/events` 응답의
`Recommendation`(D-day·다음 이벤트명·예상 할인율)에 실린다. `SaleWindow` 원본 테이블
자체(다년치 관측 로우)를 읽는 API는 없지만, 파생 예측값은 이미 프론트(WaitBuyWidget)에
뜬다. **노출 안 된 것**: 딜 신호(Reddit/Slickdeals)는 SaleEvent로 흡수될 뿐 원본
신호를 보여주는 API가 없다.

## 5. Celery 자동화 (beat_schedule)

| 태스크 | 주기 | 파일 |
|---|---|---|
| `collect_all_products` | 매일 03:00 | tasks/collect.py |
| `classify_pending` | 매시 15분 | tasks/classify.py |
| `collect_social_for_products` | 6시간마다(30분) | tasks/social_collect.py |
| `collect_reddit_signals` | 매시 5분 | tasks/reddit_signals.py |
| `collect_slickdeals_signals` | 매시 25/55분 | tasks/reddit_signals.py |
| `purge_expired_social_posts` | 매시 50분(48h 보존 강제) | tasks/reddit_signals.py |
| `extract_social_posts` | 매시 45분 | tasks/social_extract.py |
| `match_pending_products` | **6시간마다(40분)** | tasks/match_products.py — 크로스 통화 매칭 배치 |

## 6. 수집 소스 — 등록 vs 실제 활성

`collector.py`의 `SCRAPERS` 레지스트리엔 리테일 13개 + Shopify 방식 브랜드 공홈 ~25개가 등록돼 있지만, `config.py`의 `enabled_scrapers` 기본값(`"Sephora,Amazon US,Rakuten,brands"`)상 **실제 활성은 Sephora·Amazon US·Rakuten·브랜드 공홈 전체뿐**이다. 올리브영·아모레몰·쿠팡·Ulta·@cosme·Tmall·小红书는 코드는 있으나 차단 리스크로 기본 비활성(`docs/BETA-TASKS.md` T2 사유). 새 기능을 설계할 때 "이 소스에서 데이터가 온다"고 가정하기 전에 이 목록부터 확인할 것.

소셜(인스타/틱톡/페북/네이버블로그)은 각각 외부 API 키가 있어야 동작하고, 없으면 빈 결과를 조용히 반환한다.

## 7. 매칭·번역 파이프라인 핵심 함수 (B/C/D단계, 2026-08-06 랜딩)

### `app/ai/matching.py` — 순수 함수, DB/번역/LLM 미접촉
```python
def strip_noise(text: str) -> str
def containment_score(canonical: str, listing: str) -> float          # 0.0~1.0
def is_sample_listing(text: str) -> bool
def evaluate_match(
    canonical_name: str, listing_name: str, *,
    canonical_size_ml: float | None = None, listing_size_ml: float | None = None,
    canonical_unit_price: float | None = None, listing_unit_price: float | None = None,
    containment_threshold: float = 0.6, price_deviation_ratio: float = 1/3,
) -> str  # "match" | "reject" | "needs_review"
```

### `app/ai/translator.py` — 로컬 Ollama(`translategemma:4b`, 랩탑 오프로드)
```python
def translate_for_llm(text: str | None) -> str                        # 최선노력, 실패해도 원문 반환
def translate_for_matching(text: str, source_lang: str) -> str | None # 실패 시 None(캐시 안 씀)
def detect_language(text: str) -> str                                 # ja/zh/ko/en
```

### `app/ai/matcher.py` — DB 접촉, 국가 간 신규 상품 매칭(등록 시점)
```python
async def find_matching_product(db, name: str, brand: str | None, country: str) -> Product | None
async def get_or_create_product(db, name: str, brand: str | None, country: str) -> Product
```

### `app/tasks/match_products.py` — D단계 배치(위 셋을 조립)
```python
def match_pending_products(limit: int = 50) -> int   # Celery 진입점
async def _match_orphan(db, orphan: Product) -> None  # 고아 1건 판정+병합/보류
async def _merge_products(db, orphan: Product, canonical: Product) -> None
```

### `app/core/size.py` / `app/core/fx.py`
```python
def parse_size_ml(text: str | None) -> float | None
def sizes_match(a: float | None, b: float | None, tolerance: float = 0.08) -> bool
def convert(amount: float, from_currency: str, to_currency: str) -> float | None  # 정적 환율표, KRW 피벗
```

## 8. 수익화 구현 현황

- **프리미엄**: `core/premium.py` — `X-Premium-Key` 헤더를 `settings.premium_api_keys`(콤마구분 사전발급 목록)와 대조. **결제 시스템·구독 DB 없음.**
- **광고**: `AdSlot.tsx` 컴포넌트(무료 유저 노출) — 광고 네트워크 연동부는 이 세션에서 조사 안 됨, 확인 필요.
- **제휴**: `core/affiliate.py`의 `to_affiliate_url()` — Amazon US(`tag` 파라미터, **태그 미발급**), 쿠팡(`lptag`, TODO — 실제 Partners API 미연동), Rakuten(연동됨, `hb.afl.rakuten.co.jp` 래핑). 파트너 ID 미설정 플랫폼은 원본 URL 그대로 반환(안전한 기본값).

## 9. 설계 문서 인덱스 (더 깊이 필요할 때)

- `docs/design-cross-currency-matching-2026-08-05.md` — 매칭 설계 4차 실측
- `docs/plan-cross-currency-matching-2026-08-06.md` — A~D단계 실행계획(전부 랜딩)
- `docs/design-cross-currency-matching-d-stage-2026-08-06.md` — D단계 설계 + 적대감사 R1
- `docs/BETA-TASKS.md` — 베타 출시 전 남은 작업(T1~T5)
- `docs/schema.md`, `docs/api.md` — 기존 스키마/API 문서(이 문서 작성 시점에 최신 여부 미검증 — 대조 권장)
- `docs/frontend.md` — 기존 컴포넌트별 동작 방식 + SiteTimeline 카드 ASCII 목업(§10과 같이 볼 것)

## 10. 비주얼 레퍼런스 (실측 — 전체 `.tsx` 컴포넌트에서 클래스 직접 추출, 2026-08-07)

새 화면을 설계할 때 이 톤에서 벗어나면 "다른 앱처럼 보이는 화면"이 나온다. 추측
아님 — `frontend/src/components/*.tsx` 전체를 grep해서 실제 사용 빈도까지 확인했다.

**컬러 — 파스텔 배경(-50/-100) + 진한 텍스트(-600/-700) 조합, 의미별로 고정**
| 색 | 의미 | 실사용 예 |
|---|---|---|
| rose | 브랜드/할인 강조 (가장 많이 쓰임) | 헤더 로고 옆 태그라인, 할인율 뱃지, "지금 사세요" verdict |
| emerald | 좋은 딜/절약 | "OO에서 N% 더 저렴해요" 배너, "나쁘지 않아요" verdict |
| amber | 대기/주의 | "기다리세요" verdict, 프리미엄 배너 |
| blue | 정보/링크 | 이벤트 타입 뱃지, 피드백 버튼 |
| gray | 중립(본문·테두리·배경 대부분) | 어디에나 |
| red | 에러만 | 에러 메시지 |

**카드/뱃지**: `rounded-2xl`(주요 카드) 또는 `rounded-xl`, 뱃지는 `rounded-full`.
그림자는 `shadow-sm` 기본, 강조 카드만 `shadow-lg`. 테두리는 `border-2` + 파스텔
색(예: `border-amber-400`)으로 verdict 카드를 구분.

**타이포**: 본문 `text-xs`/`text-sm`이 압도적 다수(34/31회) — 이 앱은 정보 밀도가
높은 카드형 UI다, 큰 타이틀 위주 레이아웃이 아니다. 강조는 `font-semibold`가
기본(`font-bold`는 숫자·핵심 수치에만).

**아이콘은 이모지, 아이콘 라이브러리 없음**: 💄(로고) ✅⏳🛒(WaitBuyWidget verdict)
💡(팁 배너) 국기 이모지(플랫폼 국가 표시). 새 화면도 이 관례를 따른다 — Heroicons
같은 SVG 아이콘 세트를 새로 끌어오지 않는다.

**레이아웃**: `max-w-5xl mx-auto` 중앙 정렬, `sticky top-0` 헤더, 반응형 그리드는
`grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))`(브레이크포인트 대신
auto-fill로 처리 — `docs/frontend.md` 참고).

## 11. 화면 인벤토리 — PRD User Story → 신규 화면 매핑

| User Story | 화면 성격 | 비고 |
|---|---|---|
| (기존) 검색·비교 | 이미 있음 | 홈, 무수정 |
| US-002 매칭 검토 | **신규 화면**(어드민) | 표 + 승인/거부 버튼, `X-Admin-Secret` 게이트 |
| US-003 딜 피드 | **신규 화면** | 리스트형, 최신순 |
| US-006 인플루언서 딜 신호 | US-003 화면에 **통합**(같은 피드, 별도 화면 아님) | 소스 아이콘만 다르게 표시하면 충분 |
| US-004 매칭 커버리지 | **신규 화면 불필요** — US-002 어드민 화면 상단에 지표 카드 하나로 흡수 | |
| US-001 결제/구독 | **신규 화면**(결제 폼/구독 상태) | PG 위젯(Stripe Checkout 등) 임베드 여지 남길 것 |
| US-005 라우팅 | 화면 아님 — 위 화면들을 연결하는 인프라 | |

**결론: 새 화면은 실질적으로 3개**(매칭 검토, 딜 피드, 결제) — US-004는 기존
화면에 지표만 얹고, US-006은 별도 화면 없이 US-003에 합류한다. 외부 디자인
도구에 넘길 때 "화면 3개 + 기존 홈 1개 재사용"으로 스코프를 명시하면 과다생성을
막을 수 있다.
