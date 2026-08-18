# 설계 — platform_product_ids (외부 상품 식별자 저장) — 2026-08-09 (v5, 2026-08-18 개정 — 구현 착수 확정)

- 작성: 2026-08-09 PDT · Mac Studio (`mac.lan`)
- **개정 v2: 2026-08-18 · 랩탑(D:\dev\compa, Sonnet) · [예비 감사 R1](audit-platform-product-ids-2026-08-18-gemini-r1.md)
  반영.** P0 3건(Shopify Variant 미분리, matcher.py 4단계 지연의 런타임 크래시,
  merge 시 고아 행 방치) + P1 3건(Rakuten itemCode 셀러종속, Celery 동시성 upsert
  누락, Amazon ASIN 정규식 실패) 반영.
- **개정 v3: 2026-08-18 · 랩탑(D:\dev\compa, Sonnet) · [Codex 확인 라운드
  R2](audit-platform-product-ids-2026-08-18-codex-r2.md) 반영(판정: NEEDS_REVISION
  → 본 v3로 해소 시도).** R2가 지적한 5건 — (1) 대상 파일에 `scrapers/base.py`·
  `collector.py` 누락, (2) `ScrapedEvent` 필드·collector 저장 흐름 미명시,
  (3) fast-path 삽입 위치 미확정, (4) upsert 충돌 시 `product_id` 불일치 정책
  부재, (5) 2절 표가 아직 product.id/handle 기준 서술 — 전부 아래 4·5절과
  2절 Shopify 행에 반영. v1·v2 원안은 git history에 남아있음. 착수 재확인:
  2026-08-18 기준 origin/main·맥스튜디오 워킹디렉토리 모두 이 설계 미구현 상태.
- **개정 v4: 2026-08-18 · 랩탑(D:\dev\compa, Sonnet) · [Codex 확인 라운드
  R3](audit-platform-product-ids-2026-08-18-codex-r3.md) 반영(판정:
  NEEDS_REVISION → 본 v4로 해소 시도).** R3가 남긴 2건 — (1) `persist_events_for_product`가
  upsert의 authoritative product_id를 `SaleEvent` insert **전에** 쓰도록 순서
  미고정, (2) `_collect_platform` fast-path만 있고 일일 정기 수집의 실제
  주경로인 `tasks/collect.py:_collect_all`(브랜드 카탈로그 스윕)엔 fast-path가
  없음 — 전부 아래 4·5-3절에 반영. 문서 잔재(1·2·3절의 product.id/handle/onupdate
  표현)도 정리.
- **개정 v5: 2026-08-18 · 랩탑(D:\dev\compa, Sonnet) · [Gemini 적대감사
  R4](audit-platform-product-ids-2026-08-18-gemini-r4.md) 반영(판정:
  NEEDS_REVISION — 단 "2건만 보완하면 즉시 착수 가능"으로 명시).** R4가
  Codex 두 라운드가 놓친 신규 P0를 발견: 5-3절 upsert가 conflict된 기존
  매핑을 무조건 신뢰했는데, 그 매핑이 가리키는 product가 소프트 삭제됐으면
  매 수집마다 새 고아 Product가 생기고 이벤트는 계속 유령 상품에 붙는
  무한루프가 생김 — "기존 매핑이 이긴다" 원칙에 "단, 살아있을 때만" 예외를
  추가해 해소(5-3절 `upsert_platform_product_id` 전면 재작성). P1(공용
  helper `resolve_product_by_external_id`의 다중 variant 순회·item_code
  제외 계약 명시)도 반영. P2 2건(자체발견 2·3)은 8절에 후속 메모로 남김
  — 구현 착수를 막는 수준은 아니라고 R4가 판단했고 Sonnet 자체 컨펌에서도
  동의.
  **자체 컨펌(Sonnet, 2026-08-18)**: R1→v2→R2→v3→R3→v4→R4로 이어진 4라운드
  감사에서 두 감사자(Codex·Gemini)가 서로 다른 각도로 검증했고, 마지막
  라운드(R4)는 핵심 아키텍처 4항목을 전부 "수용"으로 판정하며 신규 발견도
  기존 설계를 뒤엎는 게 아니라 국소 수정(upsert 정책 1곳)으로 닫혔다 —
  수렴 신호로 판단해 여기서 감사 라운드를 마감하고 구현 착수로 넘어감.
  프로젝트 컨벤션상 실제 구현은 Codex(executor)가 수행 —
  `cowork/2026-08-18-platform-product-ids-handoff.md` 참고.
- Tier: **2** (`review-tiers.md` — 새 테이블+새 데이터 흐름 도입)
- 감사 라운드: 예비 감사 R1(랩맥 Gemini) → v2 → Codex R2(NEEDS_REVISION) → v3 →
  Codex R3(NEEDS_REVISION) → v4 → Gemini R4(NEEDS_REVISION, 국소 수정만) → v5 →
  **Sonnet 자체 컨펌 완료 — 구현 착수 확정**.
- 대상 파일(1단계 기준): `backend/alembic/versions/`(신규 마이그레이션),
  `backend/app/models/`(신규 모델 `platform_product_id.py`),
  **`backend/app/scrapers/base.py`(`ScrapedEvent`에 `external_id`/`id_type` 필드
  추가 — R2 지적 1)**, **`backend/app/scrapers/collector.py`(`resolve_product_by_external_id`/
  `find_by_external_id`/`upsert_platform_product_id` 추가, `_collect_platform`
  fast-path 삽입 + `persist_events_for_product` 매핑 upsert·순서 고정 — R2 지적
  2·3, R3 지적 1, R4 자체발견 1)**, **`backend/app/tasks/collect.py`(`_collect_all`
  브랜드 카탈로그 스윕에도 동일 fast-path 적용 — R3 지적 2)**,
  **`backend/app/ai/matcher.py`(Phase 2와 동시 수정 — v1의 "4단계로 지연" 방침
  폐기, 아래 4절 참고)**, `backend/app/tasks/match_products.py`(병합 시 매핑
  이전 — `_merge_products`가 이미 자동/수동 승인 양쪽에서 재사용되는 공유
  helper임을 R2에서 확인, 아래 5-2절 갱신), `backend/app/api/admin.py`(별도
  구현 불필요 — `_merge_products` 호출 경로라 5-1절 수정만으로 자동 해결)

> PRD `docs/PRD-2026-08-07.md`의 "식별자 폐기 실측" 절(2026-08-09 추가분)의 후속.
> **아주 쉽게 쓴다** — 이 문서를 처음 읽는 사람도 "뭘, 왜, 어떻게" 순서로 끝까지
> 따라갈 수 있게 목표로 한다.

---

## 0. 이 문서가 뭘 위한 것인가 (한 문단 요약)

지금 compa는 "이 한국 상품과 저 일본 상품이 같은 물건인가?"를 **이름을 보고
추측**해서 판단한다(번역 → 비슷한 단어 세기 → 애매하면 Claude에게 물어봄).
이 방식은 느리고, 틀리기 쉽고, LLM 호출이 필요해서 이번 크레딧 전소 사고의
원인 중 하나였다. 그런데 실제로는 **각 사이트가 이미 "이 상품의 진짜 번호"를
알려주고 있는데 compa가 그걸 무시하고 버리고 있었다**. 이 설계는 그 번호를
저장하는 작은 테이블 하나를 만들어서, "이름 추측" 대신 "번호 대조"로 상품을
연결하자는 것이다.

**비유**: 지금 방식은 사람 이름만 보고 "이 사람이 그 사람 맞나?"를 판단하는
것과 같다(동명이인 있으면 틀림). 이 설계는 주민등록번호(=상품 식별자)를 저장해서
대조하자는 것 — 훨씬 정확하고, 컴퓨터가 즉시 판단 가능하다(사람이 고민할 필요 없음).

---

## 1. 문제를 아주 구체적인 예시로

Tatcha라는 브랜드의 "The Dewy Skin Cream"이라는 화장품이 있다고 하자.

- **일본 Rakuten**에서 이 상품을 검색하면 API가 이렇게 응답한다:
  ```json
  {"itemName": "タチャ デューイースキンクリーム", "itemCode": "shop123:10000456", "itemPrice": 8200}
  ```
  `itemCode`가 이 상품의 고유 번호다. **이 번호는 이름이 바뀌어도(할인 이름이
  붙거나 오타가 나도) 안 바뀐다.**
- **미국 Amazon**에서 같은 상품을 검색하면 이런 링크가 온다:
  ```
  https://www.amazon.com/dp/B08XYZ1234?tag=...
  ```
  `B08XYZ1234`가 ASIN(Amazon Standard Identification Number) — 아마존 안에서
  이 상품의 고유 번호다.
- **브랜드 공홈(Shopify)**에서는 상품 목록 API(`products.json`)가 이렇게 준다:
  ```json
  {"id": 7891234567, "handle": "the-dewy-skin-cream", "title": "The Dewy Skin Cream",
   "variants": [{"id": 40111, "title": "50ml", "price": "68.00"},
                {"id": 40222, "title": "100ml", "price": "98.00"}]}
  ```
  최상위 `id`/`handle`이 아니라 **`variants[].id`**가 compa가 저장할 값이다
  (3-1절 — 화장품은 용량별 variant가 실제 판매·가격 단위라서).

**지금 compa 코드는 이 셋을 전부 읽고도 버린다.** 이름(`itemName`, `title`)만
저장하고 번호는 저장 안 한다 — 그래서 "이 세 개가 같은 상품이다"를 알아낼
방법이 이름 비교밖에 안 남는다.

**만약 이 번호들을 저장해뒀다면**: 다음에 Rakuten을 다시 수집할 때
`itemCode=shop123:10000456`가 그대로 다시 오니까, "저번에 저장한 그 상품이네"를
번호 하나 비교로 즉시 알 수 있다. 지금은 그것도 이름을 다시 비교해서 판단한다.

---

## 2. 선행조사

*(CLAUDE.md 규정: Tier 2+ 설계는 이 섹션이 필수. `scripts/design_lint.py`가
존재 여부를 검사한다.)*

**레포 내 검색:** `grep`으로 `app/**/*.py`와 `alembic/versions/*.py` 전체에서
`external_id`, `platform_id`(기존 것 확인용), `sku`, `SKU`, `gtin`, `GTIN`,
`upc`, `UPC`, `ean`, `EAN`, `asin`, `ASIN`, `item_code`, `itemCode` 검색.
**결과: 없음.** `Product` 모델(`app/models/product.py`)에는 4개 언어 이름
컬럼(`name_kr`/`name_en`/`name_jp`/`name_cn`)만 있고 외부 식별자 컬럼이 하나도
없다. `ProductMatchCandidate` 테이블은 있지만 이건 "애매한 매칭 후보를 사람이
검토하는 큐"이지 식별자 저장소가 아니다(용도가 다름 — 재사용 불가, 새로 만들어야
함). Sephora 스크래퍼(`app/scrapers/us/sephora.py:77`)가 `currentSku`를 읽고
있긴 한데 가격 파싱에만 쓰고 저장은 안 한다 — 이것도 "식별자를 받고 버리는" 같은
패턴의 증거.

**외부 선행작업:** 아래 4건을 확인했다(전부 확인일 2026-08-09). "최근 커밋일"은
이 넷이 오픈소스 저장소가 아니라 API 공식 문서/국제 표준이라 해당 없음 — 대신
문서 최종 확인일을 적었다.

| 이름 | URL | 라이선스/성격 | 최근 커밋일(해당 없음 — 확인일로 대체) | 채택 판단 |
|---|---|---|---|---|
| **GTIN/UPC/EAN/JAN 표준** | [GTIN vs UPC vs EAN vs ASIN 개요](https://www.bebolddigital.com/blog/gtin-vs-upc-vs-ean-vs-asin-understanding-barcode-basics) | 국제 바코드 표준(오픈 표준, 라이선스 없음 — 누구나 쓸 수 있는 공개 규격) | 확인일 2026-08-09 | **채택** — "같은 물건이면 같은 번호"라는 설계 원칙 자체를 이 표준에서 가져온다. 단, 화장품은 브랜드 공홈 상품에 바코드가 API로 노출 안 되는 경우가 많아 **보조 식별자**로만 쓴다(1순위 아님) |
| **가격추적 업계 관행(Apify 상용 스크레이퍼 사례)** | [Cross-Retailer Price Comparison](https://pagecrawl.io/blog/cross-retailer-price-comparison-product-monitoring), [GTIN 기반 매칭](https://www.minderest.com/blog/google-shopping-ean-upc-gtin-scraping) | 상용 SaaS, 코드 비공개(재사용 대상 아님 — 라이선스 확인 불필요, 코드를 안 가져오므로) | 확인일 2026-08-09 | **패턴만 참고, 코드 미채택** — 핵심 관행: "UPC/EAN/GTIN/MPN으로 먼저 대조하고, 그게 없을 때만 이름+브랜드 조합으로 대조하며, 그마저 애매하면 그때만 AI로 확인한다." 이 우선순위(식별자 → 이름 조합 → AI)를 그대로 채택 |
| **Shopify Storefront/Admin API의 SKU/variant id** | [ProductVariant - Storefront API](https://shopify.dev/docs/api/storefront/latest/objects/ProductVariant) | Shopify 공식 API 문서(무료 공개 사용, 라이선스 이슈 없음 — API 스펙일 뿐 코드가 아님) | 확인일 2026-08-09 | **채택(v3 정정)** — v1은 `products.json` 최상위 `id`(상품 고유)와 `handle`을 쓰려 했으나, R1 감사 이후 **`variants[].id`(variant 고유)**로 정정했다. 이유: 화장품은 용량별 variant가 실제 판매 단위이고 `size_ml`이 `SaleEvent` 단위 컬럼이라(3-1절), 식별자도 그 결과 레코드가 실제로 갖고 있는 variant 단위와 맞춰야 코드에 자연스럽게 흘러간다. `handle`은 가변 URL slug라 식별자로 미채택 |
| **Rakuten Ichiba Item Search API의 itemCode** | [공식 문서](https://webservice.rakuten.co.jp/documentation/ichiba-item-search) | 공개 API 스펙, 라이선스 이슈 없음 | 확인일 2026-08-09 | **채택** — 문서에 `itemCode`가 검색 파라미터이자 응답 필드로 명시. 장기 안정성(번호가 안 바뀌는지)에 대한 공식 보증 문구는 못 찾았으나(문서에 명시 없음), 업계 표준 관행상 상품 고유 코드는 변하지 않는 게 일반적 — **채택하되 "값이 바뀌면 새 상품으로 오인식할 수 있다"는 리스크를 아래 "리스크" 절에 남긴다** |
| **Amazon ASIN** | 자체 지식(공식 문서 접근은 PA-API 키 필요, 이 세션에선 URL 패턴만 확인) | Amazon 공식 식별자 | 확인일 2026-08-09 | **채택** — `DetailPageURL` 응답에서 `/dp/ASIN코드` 패턴으로 정규식 추출 가능(이미 URL을 저장하고 있으니 추출만 추가) |

**결론:** 개선해서 채택한다. 새로 발명하지 않는다 — 업계가 이미 쓰는 순서
(식별자 우선 → 이름 조합 → 그래도 애매하면 사람 검토)를 그대로 가져오고, 우리
소스들이 이미 API 응답에 갖고 있는 필드(Rakuten `itemCode`/Amazon `ASIN`/
Shopify `variant.id`)를 저장하는 작은 테이블 하나만 새로 만든다(Shopify는
v3에서 `handle`→`variant.id`로 정정 — 3-1절). LLM은 이 설계에 등장하지
않는다(PRD의 "LLM 공급 정책" 절과 일치).

---

## 3. 무엇을 만드는가 — 테이블 하나 (v2: 감사 반영)

새 테이블 이름: `platform_product_ids`

| 컬럼 | 뜻 | 예시 값 |
|---|---|---|
| `id` | 이 행 자체의 번호(내부용) | (자동생성 UUID) |
| `product_id` | compa의 `products` 테이블 어느 행인지 (FK, `ON DELETE CASCADE`) | (Tatcha Dewy Skin Cream의 UUID) |
| `platform_id` | 어느 사이트의 번호인지 — **v1의 `platform_name: String` 대신 `platforms.id` FK** ([지적 7]: 문자열은 `platforms` 테이블과 정합성이 끊기고 이름 변경에 취약) | `platforms.id`의 UUID |
| `external_id` | 그 사이트가 준 진짜 번호 | `"shop123:10000456"`, `"B08XYZ1234"`, `"40111"` |
| `id_type` | **신규 컬럼([지적 1] 반영)** — 식별자가 어느 레벨인지 명시 | `"variant_id"`, `"asin"`, `"item_code"`, `"jan"` |
| `created_at` | 언제 처음 저장했는지 | (자동) |
| `last_seen_at` | **신규 컬럼([자체발견 3] 반영)** — 마지막으로 이 식별자를 관측한 시각 | (`server_default=func.now()`로 생성, **ORM `onupdate`가 아니라 upsert의 `set_={"last_seen_at": func.now()}`에서 직접 갱신** — [R3 지적 P2], 5-3절 코드 참고) |

**유니크 제약**: `(platform_id, external_id)` — 같은 사이트의 같은 번호가 두
상품에 붙으면 안 되니까.
**인덱스**: `product_id`에 단독 인덱스 추가 ([지적 7] — 역방향 조회 풀스캔 방지,
병합·삭제·관리자 조회에서 상시 사용).

### 3-1. [지적 1, P0] Shopify는 반드시 `variant.id`를 저장한다 — `product.id`가 아니다

v1은 `products.json` 최상위 `id`(Product ID)를 저장하려 했다. **v3 정정**
(코드 재확인 결과, v2의 "즉시 유니크 위반 크래시" 서술은 부정확했다 —
`group_events_by_product_name`이 같은 `product_name`의 이벤트를 이미 한
그룹으로 묶어 `get_or_create_product`를 그룹당 1번만 호출하므로, product.id를
저장해도 같은 그룹 안에서는 매번 같은 값·같은 product_id라 그 자체로는
충돌하지 않는다. 실제 근거는 아래):
- `backend/app/scrapers/brands/shopify.py`가 만드는 `ScrapedEvent`는 이미
  variant 단위(용량별 `size_ml`, `sale_price`)로 나뉘어 있다 — product.id는
  이 레코드가 실제로 들고 있는 데이터 단위가 아니다. product.id를 쓰려면
  파싱 코드에 없는 값을 별도로 끌어와야 해서 불필요한 결합이 생긴다.
- variant.id가 더 세밀한 단위라 "이 특정 용량 리스팅"을 정확히 가리킨다 —
  브랜드가 새 색상 variant를 추가/삭제해도 다른 variant.id는 안 바뀐다.
**결정: `external_id = variant.id`, `id_type = "variant_id"`.** `handle`은
저장하지 않는다(가변 URL slug, 식별자로 부적합 — 감사 근거 그대로 수용).

### 3-2. [지적 4, P1] Rakuten `itemCode`는 "글로벌 상품 식별자"가 아니라
"셀러별 리스팅 식별자"다

`itemCode`는 `shopCode:itemUrl` 구조 — 오픈마켓이라 같은 상품도 셀러마다
값이 다르다. v1의 "번호가 새 번호면 100% 신규 확정" 전제는 **Shopify/Amazon
에는 맞지만 Rakuten에는 안 맞는다.** Rakuten 행은 "이 상품이 새 상품이다"의
증거가 아니라 "이 셀러가 이 상품을 판다"의 기록으로만 쓴다 — 신규 Product
자동생성의 판단 근거에서 Rakuten `itemCode`는 제외하고, 이름 매칭(기존 로직)에
계속 의존한다. `id_type = "item_code"`로 명시해 이 한계를 코드 레벨에서도
드러낸다. **후속 조사(범위 밖, TODO)**: Rakuten API가 JAN 코드(13자리 바코드)를
필드로 주는지 확인 — 준다면 그게 진짜 글로벌 식별자 후보(`id_type="jan"`).

### 3-3. [지적 6, P1] Amazon ASIN — URL 정규식이 아니라 필드/속성에서 직접 추출

v1은 "DetailPageURL에서 정규식으로 추출, 리스크 거의 없음"이라 썼다. 틀렸다 —
`backend/app/scrapers/us/amazon.py`의 HTML 폴백 경로는 스폰서/리다이렉트
링크(`/sspa/click?...`, `/gp/slredirect/...`)나 검색 페이지 URL로 폴백되는
경우가 있어 정규식이 실패한다.
**결정**:
- PA-API 경로: 응답의 `item["ASIN"]` 필드를 직접 읽는다(정규식 불필요).
- HTML 폴백 경로: 검색 결과 컨테이너의 `data-asin` 속성을 1순위로 읽는다.
  둘 다 실패하면 `external_id`를 저장하지 않는다(그 행은 이름 매칭에만 의존 —
  실패를 조용히 삼키고 확인 안 된 값을 저장하지 않는다).

**이 테이블이 생기면 뭐가 달라지나** (Shopify/Amazon처럼 신뢰 가능한 식별자에
한함 — Rakuten은 위 3-2 참고):

| | 지금 | 이 테이블이 생긴 후 |
|---|---|---|
| Shopify 공홈을 다시 수집할 때 | 상품 이름을 정규화해서 기존 상품과 비교(느림, 가끔 틀림) | `(platform_id, external_id)`가 일치하는 행이 있는지 딱 한 번 조회(빠름, 절대 안 틀림) |
| 신규 Shopify/Amazon 상품 발견 | 이름만 보고 신규인지 기존인지 애매하면 Claude에게 물어봄 | 번호가 새 번호면 100% 신규 확정, LLM 안 부름 |
| Rakuten 재수집 | 이름 매칭(현행 유지) | 이름 매칭(현행 유지) — `platform_product_ids`는 "이 셀러가 파는 중" 기록용 |
| 매칭 실패로 인한 중복 생성 | 종종 발생(로그에 흔적 있음) | Shopify/Amazon 소스는 크게 감소, Rakuten은 기존 수준 유지 |

---

## 4. 구현 순서 — Working Skeleton First (v2: [지적 2] 반영 — 4단계 지연 폐기)

**1단계 (제일 쉬움, 먼저)**: 테이블만 만든다(Alembic 마이그레이션 — `platform_id`
FK, `id_type`, `last_seen_at` 포함한 v2 스키마). 아무 스크래퍼도 아직 안 건드림.

**2단계 — Shopify 공홈 + matcher.py 조회 로직, 반드시 동시 배포**
([지적 2, P0] 핵심 수정: v1은 이걸 "4단계, 나중"으로 미뤘는데 그러면 안 된다.
이유 — Shopify 상품명이 리브랜딩·시즌 문구로 조금이라도 바뀌면 이름 매칭이
실패해 `get_or_create_product`가 새 Product를 만든다. 그 새 Product에
과거와 동일한 external_id가 다시 관측되면(예: 재수집 시 같은 variant.id) —
매핑 upsert가 기존에 다른 product_id를 가리키던 행과 충돌한다(정확한 처리는
아래 4번·5-3절). "데이터만 조용히 쌓인다"는 v1의 전제는 틀렸다 — 쓰기만 하고
읽지 않는 테이블은 이름 매칭이 흔들릴 때마다 자기 자신과 어긋난다.):

**정확한 코드 삽입 지점(R2 확인 반영)** — 현재 흐름은
`collector.py:_collect_platform` 안에서 `group_events_by_product_name`으로
스크래핑 결과를 상품명별로 묶고, 그룹당 **한 번** `get_or_create_product`를
호출한 뒤(`collector.py:309`), 그 `Product`와 그룹의 이벤트 전체를
`persist_events_for_product`에 넘겨 이벤트별로 `SaleEvent`를 insert한다.
즉 product 단위 판단(fast-path)과 event 단위 저장(매핑 upsert)의 위치가
다르다 — 이 둘을 각각 정확히 지정한다:

1. `backend/app/scrapers/base.py`의 `ScrapedEvent`에 필드 추가:
   `external_id: str | None = None`, `id_type: str | None = None`.
2. `backend/app/scrapers/brands/shopify.py`의 `parse_products`가 variant
   루프 안에서 `external_id=str(variant.get("id"))`, `id_type="variant_id"`를
   `ScrapedEvent`에 채워 넣는다.
3. **Fast-path 위치 — `collector.py:_collect_platform`, `get_or_create_product`
   호출 직전(그룹당 1번, 현재 309행 자리)**: 공용 helper
   `resolve_product_by_external_id(db, platform.id, events)`(5-3절 — 그룹의
   모든 이벤트를 순회하며 `find_by_external_id` 시도, `item_code`는 건너뜀)를
   먼저 호출한다. 찾으면 그 `Product`를 그대로 쓰고 `get_or_create_product`
   (이름 매칭·LLM)를 **스킵**한다. 못 찾으면 기존대로 `get_or_create_product`로
   폴백.
4. **매핑 upsert 위치 및 순서 — `persist_events_for_product`, 이벤트별
   `SaleEvent` insert 각각의 직전([R3 지적 1] 반영 — v3는 "같은 루프 안"까지만
   말하고 순서를 안 고정해 잘못된 product_id로 먼저 저장될 여지가 있었다)**:
   각 이벤트 `s`를 순회할 때 —
   1. `s.confidence == 0.0`이면 기존대로 skip.
   2. `s.external_id`가 있으면 **먼저** `upsert_platform_product_id(db, product.id, platform.id, s.external_id, s.id_type)`
      (5-3절)를 호출하고 반환값(authoritative product_id)을 받는다.
   3. 그 반환값을 이번 `SaleEvent.product_id`로 쓴다(함수 인자로 받은
      `product.id`를 그대로 믿지 않는다 — 반환값이 다르면 그게 맞는 값이다).
   4. `s.external_id`가 없으면 기존대로 `product.id` 사용.
   5. 반환값이 인자로 받은 `product.id`와 다르면 `logger.warning`으로
      재귀속 발생을 남긴다(운영 가시성 — 이후 5-1절 병합이 이 로그를 안
      봐도 자연 정리되지만, 빈발하면 이름 매칭 튜닝 신호).
   `on_conflict_do_update` 사용 — Celery 동시 실행 시 경쟁 상태로 죽지
   않게([지적 5, P1]).
5. **`tasks/collect.py:_collect_all`(브랜드 카탈로그 정기 스윕)에도 동일
   fast-path 적용([R3 지적 2] — 이 함수가 일일 수집의 실제 주경로다)**:
   현재 `_collect_all`은 `product_name, group`마다 `find_exact_for_sweep(db,
   product_name, brand)`(엄격 이름매칭 전용, 실패 시 `skipped_groups += 1`
   하고 이벤트를 통째로 버림 — 신규 생성 안 함, 스윕의 의도된 설계)만 쓴다.
   여기에 3번과 **같은 공용 helper** `resolve_product_by_external_id`를
   `find_exact_for_sweep` 호출 **전에** 끼워 넣는다 → 찾으면 그 Product로
   확정하고 `find_exact_for_sweep` 스킵 → 없으면 기존대로 `find_exact_for_sweep`
   (그래도 실패하면 기존과 동일하게 skip, 스윕은 여전히 신규 생성 안 함).
   이래야 상품명이 리브랜딩으로 바뀌어도(스윕이 원래 제일 취약한 지점)
   external_id로 계속 갱신된다 — 이게 이 설계의 핵심 동기(0. 문단)와
   가장 직접 맞닿는 경로인데 v3까지는 빠져 있었다.
   `_collect_platform`과 이 fast-path 판단 로직은 **공용 helper 함수**
   (`resolve_product_by_external_id` 같은 이름)로 추출해 두 호출부가
   같은 코드를 쓰게 한다 — 로직 중복·drift 방지.
6. `catalog.py`의 초기 시딩도 3·4·5번과 같은 fast-path/upsert 함수를
   재사용하도록 정합화([자체발견 1] — 시딩 중 variant 여러 개가 겹쳐도
   크래시하지 않게).

**3단계**: Rakuten, Amazon 순서로 같은 스크래퍼 확장 추가. Rakuten은 3-2절
한계 때문에 `get_or_create_product`의 "즉시 확정" 분기에서 **제외**하고
`id_type="item_code"`로만 기록(추후 셀러 분석·JAN 코드 후속 조사용).

**4단계(이 설계 범위 밖, 후속 설계로 분리)**: JAN 코드 등 진짜 글로벌
Rakuten 식별자 조사, 오래된 셀러 리스팅 정리(TTL/last_seen_at 기반 아카이빙 —
[자체발견 3] 대응).

---

## 5. 병합·동시성·수동승인 — v1에 없던 3개 경로 (감사 [지적 3][지적 5][자체발견 2])

### 5-1. [지적 3, P0] 상품 자동 병합 시 매핑 이전

`backend/app/tasks/match_products.py`의 `_merge_products`는 현재
`orphan.deleted_at`을 찍고 `SaleEvent.product_id`만 canonical로 옮긴다.
`platform_product_ids`는 손대지 않아 — 병합 후에도 삭제된 orphan을 가리키는
유령 매핑이 남고, 다음 수집에서 그 external_id를 다시 만나면 죽은 Product를
참조하거나(조회 조건에 `deleted_at IS NULL`이 있다면) 재차 신규 생성을 시도해
또 유니크 위반이 난다. **수정**: `_merge_products`에 아래 로직 추가 —
canonical에 이미 있는 `(platform_id, external_id)`는 orphan 쪽을 버리고
(중복 방지), 나머지는 orphan → canonical로 `UPDATE`.

```python
# orphan의 platform_product_ids 중 canonical에 이미 있는 (platform_id, external_id)는 버리고,
# 나머지는 canonical로 소유권 이전.
await db.execute(
    delete(PlatformProductId).where(
        PlatformProductId.product_id == orphan.id,
        tuple_(PlatformProductId.platform_id, PlatformProductId.external_id).in_(
            select(PlatformProductId.platform_id, PlatformProductId.external_id)
            .where(PlatformProductId.product_id == canonical.id)
        ),
    )
)
await db.execute(
    update(PlatformProductId)
    .where(PlatformProductId.product_id == orphan.id)
    .values(product_id=canonical.id)
)
```

### 5-2. [자체발견 2, P0 — R2에서 실제 경로 확인 완료] 관리자 수동 병합 승인은
별도 구현이 필요 없다

**v3 정정**: R2가 실제 코드를 확인한 결과 `backend/app/api/admin.py`의 수동
승인 API는 별도 병합 로직이 아니라 `_merge_products`를 **그대로 import해서
호출**한다. 즉 자동 매칭 경로(`_match_pending_products`)와 관리자 수동 승인
경로가 이미 하나의 공유 함수를 쓰고 있다 — 5-1절에서 `_merge_products`에
매핑 이전 로직을 추가하면 **양쪽 경로가 동시에 해결된다.** v2의 "별개
경로라면 재사용해야 한다"는 조건부 서술은 불필요했다(가정이 아니라 이미
사실로 확인됨). 별도 작업 항목 아님 — 5-1절 구현이 곧 이 항목의 구현이다.

### 5-3. [지적 5, P1 + R2 지적 4 + R4 자체발견 1, P0] 동시 쓰기는 upsert로,
단 product_id 불일치는 조용히 덮지 않는다 — 단 삭제된 상품은 예외

v2는 conflict 시 `last_seen_at`만 갱신했는데, R2가 지적한 대로 이건 **관측
갱신과 정합성 충돌을 구분하지 못한다.** 같은 `(platform_id, external_id)`가
이미 product P1을 가리키는데 이번 호출이 P2에 붙이려 하면, 그건 흔한 "같은
값 재관측"이 아니라 "둘 중 하나가 틀렸다"는 신호다(대개는 이름 매칭이 P2를
잘못 새로 만든 경우). **정책: `product_id`가 다르면 upsert가 조용히 이기지
않는다 — 기존 매핑의 product_id를 그대로 authoritative로 인정하고, 이번
이벤트도 그 기존 product로 재귀속시킨다.**

**v5 정정(R4 자체발견 1, P0)**: 위 정책에는 구멍이 있었다 — "기존 매핑의
product_id가 authoritative"가 **그 product가 소프트 삭제된 경우에도** 무조건
적용되면, `find_by_external_id`(활성 상품만 조회)는 매번 그 상품을 못 찾아
`None`을 반환하고, 폴백으로 새 Product가 매번 생성되는데, upsert는 매번
삭제된 옛 product_id를 반환해 SaleEvent가 계속 유령 상품에 붙는다 — **매
수집마다 빈 고아 상품이 하나씩 늘어나는 무한루프.** 원인: 읽기 경로
(`find_by_external_id`)는 `deleted_at IS NULL`을 걸러내는데 쓰기 경로
(upsert)는 안 걸러냈다 — 이 비대칭이 버그다. **수정 정책: 기존 매핑이
가리키는 product가 이미 삭제됐다면, 그때는 예외적으로 새 product_id가
이긴다**(소유권 재할당) — "정합성 충돌 시 기존이 이긴다"는 원칙은 기존
product가 **살아있을 때만** 적용된다.

```python
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

async def upsert_platform_product_id(
    db: AsyncSession, product_id: uuid.UUID, platform_id: uuid.UUID,
    external_id: str, id_type: str,
) -> uuid.UUID:
    """매핑을 upsert하고 최종적으로 authoritative한 product_id를 반환한다.

    - 기존 매핑이 없으면: 그대로 insert.
    - 기존 매핑이 있고 그 product가 살아있으면: product_id는 그대로 두고
      last_seen_at만 갱신 — 기존 product_id가 이긴다(정합성 충돌 시 조용한
      재귀속 방지, R2 지적 4).
    - 기존 매핑이 있는데 그 product가 이미 소프트 삭제됐으면: 새
      product_id로 소유권을 재할당한다(R4 자체발견 1 — 안 하면 매 수집마다
      고아가 하나씩 늘어나는 무한루프가 생긴다).

    호출자는 반환값을 실제 SaleEvent 저장에 쓸 product_id로 다시 사용해야
    한다(자신이 넘긴 product_id를 그대로 믿지 말 것).
    """
    existing = (
        await db.execute(
            select(PlatformProductId.product_id, Product.deleted_at)
            .join(Product, Product.id == PlatformProductId.product_id)
            .where(
                PlatformProductId.platform_id == platform_id,
                PlatformProductId.external_id == external_id,
            )
        )
    ).first()

    if existing is not None:
        existing_product_id, deleted_at = existing
        if deleted_at is None:
            await db.execute(
                update(PlatformProductId)
                .where(
                    PlatformProductId.platform_id == platform_id,
                    PlatformProductId.external_id == external_id,
                )
                .values(last_seen_at=func.now())
            )
            return existing_product_id
        # 기존 product가 삭제됨 — 새 product_id로 재할당.
        await db.execute(
            update(PlatformProductId)
            .where(
                PlatformProductId.platform_id == platform_id,
                PlatformProductId.external_id == external_id,
            )
            .values(product_id=product_id, last_seen_at=func.now())
        )
        return product_id

    stmt = pg_insert(PlatformProductId).values(
        product_id=product_id, platform_id=platform_id,
        external_id=external_id, id_type=id_type,
    ).on_conflict_do_nothing(index_elements=["platform_id", "external_id"])
    await db.execute(stmt)
    return product_id


async def find_by_external_id(db: AsyncSession, platform_id: uuid.UUID, external_id: str) -> Product | None:
    """external_id 하나로 활성 상품 조회. resolve_product_by_external_id가 호출한다."""
    result = await db.execute(
        select(Product)
        .join(PlatformProductId, PlatformProductId.product_id == Product.id)
        .where(
            PlatformProductId.platform_id == platform_id,
            PlatformProductId.external_id == external_id,
            Product.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def resolve_product_by_external_id(
    db: AsyncSession, platform_id: uuid.UUID, events: list[ScrapedEvent],
) -> Product | None:
    """이벤트 그룹(한 product_name 그룹의 모든 variant)을 순회하며 fast-path 조회.

    R4 자체발견[검증 1] 반영 — _collect_platform과 _collect_all 양쪽에서
    공용으로 호출한다(4절 3·5번). 계약:
    - Rakuten `item_code`는 신뢰 불가 식별자라 건너뛴다(3-2절).
    - 그룹 안 여러 variant 중 하나라도 기존 활성 상품에 매핑돼 있으면
      그 상품을 즉시 반환한다(50ml는 신규, 100ml는 기존인 케이스 대응).
    """
    for s in events:
        if not s.external_id or s.id_type == "item_code":
            continue
        prod = await find_by_external_id(db, platform_id, s.external_id)
        if prod is not None:
            return prod
    return None
```

---

## 6. 리스크 (v5 갱신)

- **`(platform_id, external_id)` 매핑이 서로 다른 product_id를 두고 경합하면**
  5-3절 정책대로 기존 매핑이 이긴다 — 즉 "나중에 온 이벤트가 이름 매칭으로
  잘못 만든 새 Product"는 매핑을 못 얻고 다음 배치 정리에 맡겨진다. 이건
  안전한 쪽으로 실패하는 설계지만, 정말로 상품이 개명·재출시돼서 새
  external_id로 넘어간 정당한 케이스라면 사람이 `ProductMatchCandidate`
  큐에서 판단해야 한다(자동 해소 안 됨, 의도된 동작).
- **Rakuten `itemCode`는 셀러 종속이라 신규확정 판단에서 제외했다** — 3-2절.
  이건 v1의 "리스크"가 아니라 v1의 **설계 오류**였다(수정 완료, 항목 아님).
- **Shopify `variant.id`도 언젠가 바뀔 수 있다**: 브랜드가 상품을 삭제하고
  새로 만들면 바뀐다 — 이름 비교보다는 훨씬 드물지만 0%는 아니다. 대응:
  발생하면 `ProductMatchCandidate` 큐로 사람이 병합(5-1/5-2 경로로 매핑도
  같이 정리됨 — 이미 있는 안전망 + 이번에 고친 이전 로직).
- **`id_type` 분류가 틀리면(예: variant_id인데 product_id로 잘못 저장)** 조용히
  틀린 매칭을 만들 수 있다. 대응: 스크래퍼 단위 테스트에서 `id_type`과
  `external_id` 자릿수/형식을 함께 assert(Shopify variant id는 Product id와
  값 범위가 겹칠 수 있어 타입 태그가 없으면 구분 불가).
- **2~3단계(Shopify/Rakuten/Amazon 확장)는 matcher.py 통합까지 포함**이라
  v1보다 범위가 넓다 — "1단계만 빨리 끝낸다"는 v1의 낙관은 유효하지 않음,
  2단계부터 온전한 기능 단위로 커야 한다.

## 7. 완료 판정 (v5 갱신)

- `platform_product_ids` 테이블이 v2 스키마(`platform_id` FK, `id_type`,
  `last_seen_at` 포함)로 DB에 존재하고, `alembic upgrade head`가 에러 없이 통과
- `ScrapedEvent`에 `external_id`/`id_type` 필드가 존재하고, Shopify 스크래퍼가
  variant 루프에서 채워 넣는지 단위 테스트로 확인 ([R2 지적 1·2])
- Shopify 공홈 스윕 1회 실행 후, 같은 브랜드를 **두 번 연속** 스윕해도 2회차가
  에러 없이 통과(동시성/유니크 검증 — [지적 5])
- 서로 다른 용량(variant) 2개를 가진 실제 Shopify 상품 1개로 통합테스트 —
  두 이벤트 모두 성공 저장, `platform_product_ids`에 서로 다른 `external_id`
  2행 생성 ([지적 1] 회귀 방지)
- `_collect_platform`의 fast-path 단위 테스트: 이미 매핑된 external_id로
  재수집 시 `get_or_create_product`(이름 매칭·LLM)가 **호출되지 않고**
  `find_by_external_id`만으로 기존 Product를 반환하는지 확인 ([지적 2][R2 지적 3])
- upsert 충돌 정책 단위 테스트: **기존 product가 살아있는 상태**에서 같은
  external_id를 서로 다른 product_id로 두 번 upsert 시도 → 두 번째 호출이
  첫 번째 product_id를 그대로 반환(조용한 재귀속 없음) 확인 ([R2 지적 4] —
  기존 product가 삭제된 경우는 아래 별도 테스트, 결과가 반대이므로 혼동 금지)
- `_merge_products` 단위 테스트: orphan에 매핑이 있는 상태로 병합 실행 →
  매핑이 canonical로 이전됐는지, 중복 시 orphan 쪽이 삭제됐는지 확인, 그리고
  `admin.py`의 수동 승인 API를 통한 병합에서도 동일하게 동작하는지 확인
  (같은 함수 호출이므로 회귀 테스트 하나로 양쪽 커버 — [지적 3][자체발견 2])
- `persist_events_for_product` 순서 단위 테스트: 기존 매핑이 P1을 가리키는
  상태에서 같은 external_id를 가진 이벤트를 product=P2로 호출 → 실제
  insert된 `SaleEvent.product_id`가 P2가 아니라 **P1**인지 확인 ([R3 지적 1] —
  이게 안 되면 "조용한 재귀속 방지" 정책이 문서상으로만 존재하는 것)
- `_collect_all`(브랜드 카탈로그 스윕) fast-path 테스트: 상품명이 바뀌어
  `find_exact_for_sweep`가 실패하는 상황을 시뮬레이션해도, 이벤트에
  external_id가 있으면 `find_by_external_id`로 기존 Product를 찾아 갱신하는지
  확인 ([R3 지적 2] — 이 시나리오가 이 설계의 원래 동기 그 자체)
- **소프트 삭제 재할당 단위 테스트(R4 자체발견 1)**: 기존 매핑이 가리키는
  product를 삭제(`deleted_at` 설정)한 뒤 같은 external_id로 다시 upsert →
  새 product_id로 소유권이 재할당되는지, 그리고 이 시나리오를 두 번 연속
  반복해도 고아 Product가 매번 늘지 않는지(무한루프 회귀 방지) 확인 —
  **이 테스트 없이는 v5 착수 조건 미충족으로 간주한다.**

---

## 8. 후속 메모 (P2, 구현 착수를 막지 않음 — R4 자체발견 2·3)

- **[자체발견 2] `_collect_platform`의 `collected_product_ids` 반환 정합성**:
  `persist_events_for_product`가 이벤트를 다른 product로 재귀속시키면
  (5-3절), `_collect_platform`이 모으는 `collected_product_ids` 집합과
  실제로 이벤트가 붙은 product id가 어긋날 수 있다 — `collect_on_demand`의
  `_products_with_events` 결과에서 방금 수집된 이벤트가 누락될 위험.
  구현 시 `persist_events_for_product`가 실제 사용된 product_id 집합을
  반환하도록 시그니처를 바꾸고 `_collect_platform`이 그걸 합산하게 할 것.
- **[자체발견 3] `_match_pending_products`의 스캔 범위 재확인**: 5-3절은
  "빈 고아는 다음 배치 정리에서 자연 정리된다"고 서술하지만, 실제
  `_match_pending_products`는 `name_en IS NULL`인(=일본/한국 등 비영문
  플랫폼에서 온) 고아만 스캔한다. Shopify(미국)에서 생긴 빈 고아는 이
  배치의 대상이 아니다 — 다만 이벤트가 0개인 고아는 `_products_with_events`
  필터로 UI에 노출되지 않으므로 사용자 영향은 없다(DB에 안 쓰이는 빈 행만
  누적). 구현 시 이 스캔 범위를 넓힐지, 아니면 "이벤트 0개 고아 주기적
  정리" 배치를 별도로 둘지는 이 설계 범위 밖 — 후속 이슈로 트래킹.
