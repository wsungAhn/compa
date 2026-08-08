# 일일 수집 스코프 수정 — 브랜드 공홈 카탈로그 스윕

- 작성: 2026-08-07 PDT · Mac Studio (`mac.lan`)
- Tier: **2** (`review-tiers.md:63` — 새 데이터 흐름 도입 + 일일 persistence 동작 변경)
- 대상 파일: `app/tasks/collect.py`, `app/scrapers/collector.py`, `tests/tasks/test_collect.py`(신규)
- 워크트리: `.worktrees/collect-daily-scope` (브랜치 `design/collect-daily-scope`)

---

## 1. 문제

`collect_all_products`(Celery beat `collect-all-daily`, 매일 03:00 KST)가 활성 상품
294개 중 **4개(1.4%)만** 수집한다.

`app/tasks/collect.py:25`:

```python
select(distinct(Product.name_kr)).where(
    Product.deleted_at.is_(None), Product.name_kr.isnot(None)
)
```

`name_kr`이 있는 상품이 4개뿐이다. 나머지 290개(브랜드 공홈 시딩 269개 `name_en`,
라쿠텐 매칭 21개 `name_jp`)는 **영원히 갱신되지 않는다.**

> **선행 조건 (2026-08-08 추가)**: 이 수정보다 `design-async-engine-pool-2026-08-08.md`가
> **먼저** 랜딩돼야 한다. `collect_all_products`는 현재 성공 0 / 실패 2 — 이벤트 루프와
> 커넥션 풀 불일치로 태스크가 실행 자체를 못 한다. 스코프를 고쳐도 돌지 않는다.
>
> **수치 갱신 (2026-08-08 재실측)**: 활성 상품 294 → **303**, `name_kr` 보유 4 (1.3%),
> `name_en` 278, `name_jp` 21. Path A 커버리지 211/294 → **211/303 (69.6%)**.
> 아래 표는 08-07 시점 값이며 구현 직전에 다시 실측할 것.

### 실측 (2026-08-07, 라이브 DB)

| 항목 | 값 |
|---|---|
| 활성 상품 | 294 |
| `name_kr` 보유 | 4 (1.4%) — 그중 2개는 영어가 들어감(`'SK-II Facial Treatment Essence'`, `'starter ritual'`) |
| `name_en` / `name_jp` / `name_cn` | 269 / 21 / 0 |
| sale_event 1건 이상 보유 | 45 / 294 |
| 총 sale_events | 101건 (전부 08-05~08-06 생성) |

플랫폼별 이벤트 분포 — 상위 2개가 **비활성 플랫폼**이다:

```
올리브영 60   ← enabled_scrapers에 없음
Rakuten  28
네이버쇼핑  6  ← API 2026-07 종료 (catalog.py:3)
Amazon US 4
Sephora   1
```

---

## 2. 선행조사

- 레포 내 검색: `cross_search_symbols("seed_catalog")` → 빈 결과(compa 미색인). grep 폴백 → `scrape("")` 호출부 1건(`app/scrapers/catalog.py:43`), `_save_events` 호출부 1건(`app/scrapers/collector.py:299`), 일일 수집 태스크 테스트 **0건**. 재사용 가능한 기존 자산 확인 — 새 스크래퍼 불요
- 외부 선행작업: camelcamelcamel/Keepa 계열 가격추적기의 벌크 카탈로그 폴링 패턴 — 상품별 검색이 아니라 판매자 피드를 주기 폴링. **코드 채택 없음(패턴만 참고)이라 라이선스·커밋일 검토 불요**. Shopify `/products.json`은 플랫폼 공개 표준 엔드포인트로 이미 `shopify.py`가 사용 중
- 결론: **재사용** — `ShopifyBrandScraper.scrape("")` + `_save_events`/`find_matching_product`(전부 기존)를 잇는 배선만 추가. `_collect_platform` 내부 저장 블록은 헬퍼로 추출해 공유

상세는 아래.

### ① 레포 내 검색:

지식그래프(`agent-hub-knowledge` MCP) `cross_search_symbols("seed_catalog")` → **빈 결과**.
compa는 pm_enabled 프로젝트 목록(ai-broker/ai-feed/alphabot/trader/frankencrawler/
polypoly/agent_hub/openscience)에 없어 색인 대상이 아니다. 따라서 grep으로 폴백했고
(`graph_before_grep_guard.py`의 차단 대상도 아님을 실행으로 확인), 결과는 아래와 같다.

| 쿼리 | 결과 |
|---|---|
| `scrape("")` 호출부 | **1건** — `app/scrapers/catalog.py:43` (`seed_catalog`) |
| `_save_events` 호출부 | **1건** — `app/scrapers/collector.py:299` (`_collect_platform` 내부) |
| `tests/` 내 `collect_all` / `_collect_all` | **0건** — 일일 수집 태스크는 테스트 커버리지가 전혀 없다 |
| `tests/` 내 `seed_catalog` | 1건 — `tests/scrapers/test_catalog_seed.py` (7 케이스) |

**핵심 발견 — 필요한 데이터를 이미 받아왔다가 버리고 있다.**

`app/scrapers/brands/shopify.py:110`의 `ShopifyBrandScraper.scrape()`는
`/products.json?limit=250`으로 **브랜드 카탈로그 전체**를 받은 뒤
`parse_products`(`shopify.py:44`)가 쿼리 토큰으로 클라이언트 사이드 필터링한다.
즉 제품마다 호출하면 **같은 HTTP 응답을 N번 다시 받는다.**

그리고 `catalog.py:43`의 `seed_catalog`는 이미 브랜드당 `scrape("")` 1회씩 호출해
전체를 받아오면서, `compare_at_price`가 실린 `ScrapedEvent`를 **상품명만 뽑아 쓰고
가격을 통째로 버린다**(`catalog.py:57` — `Product(name_en=name, brand=event.brand)`).

일일 가격수집이 필요로 하는 데이터가 이미 손에 들어왔다가 폐기되는 구조다.

### ② 외부 선행작업:

가격추적 서비스의 일반적 패턴을 조사했다. **코드는 채택하지 않으므로 라이선스 검토는
불요**하며, 아키텍처 패턴만 참고한다.

| 사례 | 패턴 | 채택 여부 |
|---|---|---|
| camelcamelcamel / Keepa (Amazon 가격추적) | 상품별 검색이 아니라 **판매자 피드/벌크 엔드포인트**를 주기적으로 당겨 전량 스냅샷을 뜬다. 상품 단위 폴링은 확장이 안 된다는 것이 이 카테고리의 공통 결론 | **채택** — 본 설계의 Path A가 정확히 이 형태 |
| Shopify `/products.json` | 플랫폼이 공개적으로 노출하는 표준 카탈로그 엔드포인트. 인증 불요, 페이지당 최대 250건 | **채택** — 이미 `shopify.py`가 사용 중 |
| 리테일러 검색 스크래핑 (Sephora/Amazon UI) | 상품별 쿼리가 불가피. rate limit·봇차단이 상수 비용 | **이번 레이어에서 제외** (§7 참조) |

### ③ 결론:

**재사용한다.** 새 스크래퍼도 새 모듈도 만들지 않는다. `ShopifyBrandScraper.scrape("")`
(기존)와 `_save_events`/`get_or_create_product`(기존)를 잇는 **얇은 배선**만 추가한다.
`_collect_platform`(`collector.py:288-300`) 안에 이미 "이벤트를 상품명으로 묶어
저장"하는 로직이 있으므로 이를 헬퍼로 추출해 두 경로가 공유한다.

---

## 3. 실측한 외부 계약 (2026-08-07 라이브 26개 브랜드 전수)

과거 설계감사 실패분포 상위가 `EXTERNAL_CONTRACT_UNVERIFIED 17%`라 실물로 태웠다.

```
성공 26/26 브랜드 | 총 events=2,745 | 고유 상품명=2,388 | 할인중 events=615
```

브랜드별 편차가 크다: Westman Atelier 232건, Merit 228건 ↔ SK-II 27건, Amorepacific 29건.

**이것이 이 설계의 급소다.** `get_or_create_product`를 그대로 태우면 카탈로그가
294 → **2,388개(8배)**로 불어난다. 이는 사용자가 승인한 범위("26콜로 211개 상품
커버")를 넘어서므로, Path A는 **기존 상품 갱신만** 한다 (§4.2).

---

## 4. 설계

### 4.1 범위

| | in-scope | out-of-scope |
|---|---|---|
| 브랜드 공홈 26곳 카탈로그 스윕 → 기존 상품 가격 갱신 | ✅ | |
| 검색 플랫폼(Sephora/Amazon US/Rakuten) 갱신 | | ❌ §7-1 |
| 신규 상품 카탈로그 편입 | | ❌ §7-2 |
| `Bare Product`·해시브랜드 정크 정리 | | ❌ §7-3 |
| `collect_on_demand`의 `country="KR"` 하드코딩 | | ❌ §7-4 |

### 4.2 Path A — 브랜드 카탈로그 스윕

```
for platform_name in (enabled_scrapers ∩ BRAND_SCRAPERS):     # 26회
    events = await scraper.scrape("")                          # 카탈로그 전체
    for product_name, group in group_by_name(events):
        product = await find_matching_product(...)             # 생성하지 않는다
        if product is None:
            skipped += 1;  continue
        await _save_events(db, product, platform, group)
```

- HTTP 콜 **26회/일** (현행 116회에서 감소)
- 커버리지 **211/294 (71.8%)** — 잔여 83개는 브랜드 NULL 51 + 해시브랜드 32
- 상품 **생성 없음** — `get_or_create_product`가 아니라 `find_matching_product`
  (`matcher.py`, 기존 함수)를 쓴다. 매칭 실패는 `skipped` 카운터로 관측한다

### 4.3 공유 헬퍼 추출 (Tier 2 워크플로 B — DRY)

`collector.py:288-300`의 "이벤트를 상품명으로 묶어 저장" 블록을 추출한다:

```python
async def persist_scraped(
    db, platform, scraped, country, *, create_missing: bool
) -> tuple[set[uuid.UUID], int]:
    """스크랩 이벤트를 상품별로 묶어 저장. (저장된 product_id 집합, 스킵 수) 반환.

    create_missing=False면 기존 상품만 갱신한다 — 카탈로그 스윕은 브랜드 전량을
    받아오므로 생성을 허용하면 한 번에 2,388행이 들어온다(2026-08-07 실측).
    """
```

- `_collect_platform`은 `create_missing=True`로 호출 (동작 불변)
- Path A는 `create_missing=False`로 호출

이름 없는 이벤트를 거르는 가드(`collector.py:293`, 셀렉터 파손 시 정크 상품 생성 방지)는
헬퍼 안으로 그대로 옮긴다.

### 4.4 `_collect_all` 재작성

```python
async def _collect_all() -> int:
    """브랜드 공홈 카탈로그를 훑어 기존 상품의 가격을 갱신한다.

    상품마다 검색하지 않는다 — 공홈 스크래퍼는 카탈로그 전체를 한 번에 주므로
    (shopify.py:110) 상품별 호출은 같은 응답을 N번 다시 받는 것과 같다.
    """
```

반환값은 **갱신된 상품 수(int)** 유지 — Celery beat 시그니처 불변.

---

## 5. 에러 처리 (`CLAUDE.md` 절대규칙: Explicit Error Handling)

현행 `collect.py:34-36`은 예외를 로깅 없이 삼킨다:

```python
except Exception:
    continue          # ← 무엇이 몇 번 실패했는지 알 수 없다
```

신규 코드는 브랜드 단위로 `try/except` + `logger.warning(브랜드명, 예외)` + 실패 카운트를
집계해 완료 시 1줄로 남긴다:

```
INFO  brand catalog sweep: 26 brands ok=26 fail=0 | products updated=211 skipped=2177 | events saved=N
```

`skipped`가 크게 나오는 것은 정상이다(카탈로그 2,388 중 DB에 있는 211만 갱신).
이 수치가 관측되어야 §7-2 판단이 가능하다.

---

## 6. 테스트 계획 (Tier 2 워크플로 D)

`tests/tasks/test_collect.py` 신규. 기존 `tests/scrapers/test_catalog_seed.py`의
`FakeSession`/`_fake_registry` 패턴을 그대로 따른다.

| # | 케이스 | 방어하는 회귀 |
|---|---|---|
| T1 | `name_kr=None`인 상품이 갱신 대상에 **포함**된다 | **이 P0의 본질** |
| T2 | 브랜드당 `scrape()` 호출이 **정확히 1회** (call count assert) | 상품별 재호출 재발 — 호출 수를 세지 않으면 안 보인다 |
| T3 | DB에 없는 카탈로그 상품은 저장되지 않고 `skipped`로 계수된다 | 카탈로그 8배 폭증 |
| T4 | 한 브랜드가 예외를 던져도 나머지 25개가 진행되고, 그 사실이 로깅된다 | 조용한 전량 실패 |
| T5 | `product_name`이 빈 문자열/공백인 이벤트는 저장되지 않는다 | 셀렉터 파손 시 정크 행 |
| T6 | `create_missing=True` 경로(`_collect_platform`)의 기존 동작이 불변 | 헬퍼 추출 회귀 |

베이스라인: 현재 `484 passed` (직전 세션 실측). 머지 전 `pytest -q` + `mypy --strict app/` 필수.

---

## 7. Out-of-scope — 후속 레이어

1. **검색 플랫폼 갱신 (Sephora/Amazon US/Rakuten)** — 실측 결과 실효 대상이 6개뿐이다.
   이벤트 보유 45개 중 `Bare Product` 더미 18개, `name_jp` 21개는 라쿠텐 **리스팅
   원제목**(`【送料無料】SK-II フェイシャル トリートメント エッセンス 75ml SK2 …`)이라
   검색어로 쓰면 0건이 나온다. **선행조건: 정규 제품명 확보** (아래 2번).

2. **정본 카탈로그 레이어** — 공홈 정본명은 깨끗하다(실측: `PITERA™ Facial Treatment
   Essence` × 4사이즈). 정본이 생기면 매칭이 리스팅×리스팅(N×N) → 리스팅×정본(N×1)로
   줄고, `SK-II-<해시>` 브랜드 32개로 흩어진 현상도 해소된다. **설계 질문: 정본 2,388건을
   `products`에 넣을 것인가(8배) 별도 테이블로 둘 것인가.** 별도 설계문서 대상.
   - 부수 발견: 사이즈 파싱률이 브랜드별 9.2%~70.4%로 편차가 크다(Merit 9.2%,
     Laneige 16.1% — variant title이 색상인 경우). `size_ml=None`이면
     `sizes_match`가 True를 반환하므로(`size.py:78`) 파싱 실패 = 사이즈가 변별력
     상실. 색조 브랜드에서 오매칭 위험. 정본 레이어에서 같이 다룬다.
   - 사이즈 **환산**은 이미 정상이다: fl oz→ml 환산값 73.9ml과 라쿠텐 표기 75ml이
     `sizes_match(tolerance=0.08)` 기준 1.5% 차이로 통과한다(159.7/160, 227.7/230,
     325.3/330 동일). 손댈 곳이 아니다.

3. **카탈로그 정크 정리** — `Bare Product xxxx` 18행, `SK-II-<해시>` 브랜드 32행.
   데이터 삭제라 Gate Before Irreversible 대상. 사용자가 2번을 우선한다고 명시(08-07).

4. **`collect_on_demand`의 `country="KR"` 하드코딩** — `collector.py:353`이 검색어와
   무관하게 항상 `get_or_create_product(db, query, None, "KR")`로 seed 상품을 만든다.
   영문 검색어가 `name_kr`에 들어가는 원인(실측: `name_kr='SK-II Facial Treatment
   Essence'`, `'starter ritual'`). 사용자 검색 경로에만 남는 문제라 Path A와 무관하다.

---

## 8. 설계 부채 트레이드오프 (Tier 2 워크플로 C)

**`create_missing=False`를 택한 대가**: 브랜드 공홈에 새로 올라온 상품은 `seed_catalog`를
수동 실행하기 전까지 추적되지 않는다.

**그 대신 얻는 것**: 일일 태스크가 카탈로그 크기를 바꾸지 않는다는 불변식. 카탈로그
확장은 `seed_catalog`(`MAX_PER_BRAND=100`, beat 미등록 = 수동 트리거)라는 **이미 존재하는
사용자 통제 레버**에 남는다. 수집 경로와 확장 경로를 섞지 않는 편이 §7-2 결정 전까지
되돌리기 쉽다.

**부채가 되는 조건**: §7-2에서 "정본을 products에 넣는다"로 결정되면 이 플래그는
불필요해진다. 그때 `create_missing` 인자를 제거하는 것이 Delete, Don't Deprecate에
맞는 처리다.

---

## 9. 성능 (Tier 2 워크플로 E)

| | 현행 | 변경 후 |
|---|---|---|
| HTTP 콜/일 | 4 상품 × 29 플랫폼 = 116 | **26** |
| 실효 커버리지 | 4 상품 | **211 상품** |
| (참고) 필터만 제거했을 때 | 294 × 29 = **8,526** | — |

- `_save_events`가 이벤트마다 `_is_duplicate` 쿼리를 1회 돈다 → 2,745 이벤트 기준
  N+1. 단 §4.2에서 DB에 없는 상품은 `_save_events`에 도달하지 않으므로 실제 쿼리는
  211개 상품에 걸린 이벤트로 한정된다. 현 규모에서 최적화 불요, 정본 레이어에서
  전량 저장으로 바뀌면 재검토.
- `_is_duplicate`는 `start_date`를 시그니처에 포함하고 공홈 이벤트는
  `start_date=date.today()`(`shopify.py:88`)라 **매일 새 행이 쌓인다**. 이는 가격
  이력 축적이라는 의도된 동작이다. 211상품 기준 연 ~7만 행 규모.

---

## 10. 검증 절차 (Verification Before Done)

1. `pytest tests/ -q` — 484 passed 유지 + 신규 6케이스
2. `mypy --strict app/` — clean
3. **라이브 스모크**: 워크트리에서 `_collect_all()` 1회 실행 후
   - 갱신 상품 수 ≥ 200 확인
   - `products` 행 수가 294에서 **증가하지 않았음** 확인 (T3의 라이브 대응)
   - `sale_events` 신규 행의 `platform` 분포가 공홈 26곳에 걸쳐 있는지 확인
4. 머지 후 Celery beat 재시작 — 파일만 고치면 떠 있는 워커는 구코드를 물고 돈다
