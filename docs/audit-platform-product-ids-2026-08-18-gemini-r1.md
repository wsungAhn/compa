# platform_product_ids 설계 적대적 감사 보고서 — 2026-08-18

> **서열**: 이건 예비 감사다(GLM/Qwen 체인이 아니라 랩맥 Antigravity/Gemini
> 구독세션을 `agentapi`로 호출해 수행). 확정 판정은 Codex 확인 라운드 몫 —
> `heptarchy/scripts/glm_audit.py`의 감사 체인 컨벤션과 동일한 서열을 따른다.
> 착수 시점 재확인: 2026-08-18 기준 origin/main·맥스튜디오 워킹디렉토리 모두
> `c721e5c`로 동일 — 이 설계는 어디에도 구현된 적 없음(감사 대상 유효).
>
> **감사 대상 문서**: `docs/design-platform-product-ids-2026-08-09.md`
> **감사 대상 커밋**: `c721e5c`
> **감사자**: 랩맥(M1ui-Macmini) Antigravity 구독세션, `agentapi new-conversation` 호출
> **감사 기준**: 실제 백엔드 소스코드(`backend/app/` 하위 스크래퍼, 모델, 태스크, AI 매처)와의 정합성 및 런타임 무결성 검증

---

## 1. 판정 요약

| # | 지적 / 검증 항목 | 판정 | 심각도 | 핵심 이유 |
|---|---|---|---|---|
| **1** | **Shopify 식별자 레벨 오류 (Product ID vs Variant ID)** | **수용** | **P0** | 화장품은 용량별 Variant가 핵심인데 `product.id` 저장 시 다용량 등록에서 `(platform_name, external_id)` UNIQUE 충돌 발생 |
| **2** | **매처(`matcher.py`) 수정의 4단계 지연 전략** | **반려** | **P0** | 4단계 전까지 `get_or_create_product`가 새 Product를 만들면 기존 external_id와 즉시 UNIQUE 충돌을 일으켜 스크래퍼가 트랜잭션 롤백으로 크래시됨 |
| **3** | **상품 병합(`_merge_products`) 및 소프트 삭제 시 고아 행 방치** | **수용** | **P0** | Celery 병합 시 `platform_product_ids` 업데이트 누락으로 삭제된 orphan을 가리키는 유령 매핑 잔존 |
| **4** | **Rakuten `itemCode`의 글로벌 고유 식별자 가정** | **부분수용** | **P1** | `itemCode`는 오픈마켓의 셀러(`shopCode`) 종속 코드이므로 동일 제품도 셀러마다 달라 글로벌 식별자로 작동 불가 |
| **5** | **Celery 동시 스크래핑 시 `ON CONFLICT` Upsert 부재** | **수용** | **P1** | 병렬 실행(`asyncio.gather`, Celery 멀티 워커) 시 중복 인서트 경쟁 상태로 `UniqueViolation` 발생 위험 |
| **6** | **Amazon ASIN 추출의 단순 정규식 의존** | **수용** | **P1** | 스폰서 광고 URL, 검색 폴백 URL 등에서 정규식 실패. PA-API의 `ASIN` 필드 및 HTML `data-asin` 속성을 직접 사용해야 함 |
| **7** | **`platform_name` 문자열 비정규화 및 역방향 인덱스 누락** | **수용** | **P2** | 기존 `Platform` 테이블(FK)과의 정합성 단절 및 `product_id` 기준 역방향 조회 시 풀스캔 발생 |

---

## 2. 설계에서 타당하게 판단된 부분 (정당한 결정)

문제를 억지로 만들지 않고, 실제 타당한 설계 결정 3가지를 명시합니다.

1. **외부 플랫폼 고유 식별자 우선 대조(Identifier-First) 아키텍처**
   - **근거**: `backend/app/ai/matcher.py:187-292`
   - **평가**: 현재 매칭기는 문자열 정규화 후 Claude LLM fallback을 거치므로 LLM 크레딧 소모와 지연시간이 큼. 플랫폼이 발급한 고유 번호를 최우선 대조 키로 사용하여 O(1) 매칭을 유도하는 방향성은 전적으로 타당함.
2. **독립된 1:N 매핑 테이블(`platform_product_ids`) 분리 구조**
   - **근거**: `docs/design-platform-product-ids-2026-08-09.md` 3절
   - **평가**: `products` 테이블에 `rakuten_item_code`, `amazon_asin` 등의 개별 컬럼을 추가하지 않고 별도 테이블로 뺀 것은 다국가/다플랫폼 확장에 적합한 올바른 RDBMS 설계 패턴임.
3. **Shopify 공홈 우선 적용 단계화 (Phase 2)**
   - **근거**: `backend/app/scrapers/brands/shopify.py:168-198` (26개 브랜드 레지스트리)
   - **평가**: Shopify 공홈은 봇 차단이 없고 `products.json`이라는 표준 JSON 응답을 제공하여 세일 이벤트의 86%를 차지함. 가장 안정적인 소스부터 단계적으로 도입하려는 착수 순서는 합리적임.

---

## 3. 상세 감사 지적

---

### [지적 1] Shopify 식별자 레벨 오류: Product ID vs Variant ID 불일치

- **심각도**: **P0 (정합성 차단)**
- **근거**:
  - 문서 인용: `docs/design-platform-product-ids-2026-08-09.md` 48-52행 (`"id": 7891234567, "handle": "the-dewy-skin-cream"`), 109행 (`"7891234567"`)
  - 코드: `backend/app/scrapers/brands/shopify.py:58-100` (`parse_products`)
  - 모델: `backend/app/models/sale_event.py:35-37` (`size_ml`)
- **왜 문제인가 (구체적 실패 시나리오)**:
  1. Shopify의 `products.json`에서 최상위 `id`(`7891234567`)는 **Product ID**(상품 전체 ID)이며, 그 아래 `variants` 배열에 용량별 **Variant ID**(예: 50ml는 `40111`, 100ml는 `40222`)가 존재함.
  2. `shopify.py:69-100`은 서로 다른 용량(50ml, 100ml)의 가격과 할인율이 완전히 다르므로 용량별로 각각 `ScrapedEvent`를 생성함.
  3. compa의 매칭기는 50ml와 100ml를 서로 다른 정본 `Product`로 관리하거나 개별 매칭함.
  4. 만약 설계 문서대로 최상위 Product ID(`7891234567`)나 `handle`을 `external_id`로 저장하면:
     - 50ml 이벤트 저장 시: `("Tatcha 공홈", "7891234567") -> Product A` 저장 성공.
     - 100ml 이벤트 저장 시: `("Tatcha 공홈", "7891234567") -> Product B` 저장 시도.
     - **결과**: `(platform_name, external_id)` 유니크 제약 위반(`IntegrityError`)으로 100ml 상품 수집 전체가 실패하고 롤백됨.
  5. 또한 `handle`은 마케팅/SEO 목적으로 쇼핑몰 관리자가 언제든 바꿀 수 있는 가변 URL slug이므로 고유 식별자로 부적합함.
- **수정 권고**:
  - Shopify의 `external_id`는 반드시 **`variant.id`**를 사용해야 함.
  - 스키마에 `external_id_type` 컬럼(예: `variant_id`, `product_id`, `asin`, `item_code`)을 명시적으로 추가하여 식별자 단위를 명확히 정의할 것.

---

### [지적 2] 매처(`matcher.py`) 수정의 4단계 지연 전략의 치명적 결함

- **심각도**: **P0 (정합성 차단)**
- **근거**:
  - 문서 인용: `docs/design-platform-product-ids-2026-08-09.md` 137-140행 (4단계: matcher.py 변경을 나중으로 미룸), 151-153행 ("데이터를 쌓는 단계")
  - 코드: `backend/app/scrapers/collector.py:309-310`, `backend/app/ai/matcher.py:294-347` (`get_or_create_product`)
- **왜 문제인가 (구체적 실패 시나리오)**:
  1. 설계자는 "1~3단계는 스크래퍼가 데이터만 쌓고, 매칭 로직(`matcher.py`) 수정은 4단계로 미룬다"고 설계함.
  2. 스크래퍼는 `collector.py:309`에서 `get_or_create_product`를 호출하여 반환된 `Product`에 `platform_product_ids`를 인서트함.
  3. **실제 런타임 충돌 흐름**:
     - **1일차 수집**: "SK-II 피테라 에센스" 수집 -> `get_or_create_product`가 Product P1 생성 -> `platform_product_ids`에 `("SK-II 공홈", "variant_123", P1)` 저장.
     - **2일차 수집**: 공홈에서 상품명이 "SK-II 피테라 에센스 [홀리데이 한정판]"으로 미세하게 변경됨.
     - `get_or_create_product`는 여전히 4단계 이전이므로 `external_id`를 조회하지 않고 이름 기반 매칭(`find_matching_product`)을 수행함.
     - 이름 차이로 매칭 실패 또는 Claude 호출 실패 발생 -> `get_or_create_product`가 새 Product **P2**를 생성!
     - 스크래퍼가 `("SK-II 공홈", "variant_123", P2)`를 `platform_product_ids`에 삽입 시도.
     - **결과**: DB에 이미 `("SK-II 공홈", "variant_123", P1)`이 존재하므로 **`UniqueViolation` 에러가 발생하여 2일차 스크래핑 트랜잭션 전체가 크래시 및 롤백**됨!
  4. 따라서 4단계를 미루면 "조용히 데이터가 쌓이는 것"이 아니라, 매칭기가 새 Product를 만드는 즉시 DB 제약 위반으로 스크래퍼가 폭파됨.
- **수정 권고**:
  - `matcher.py`의 `get_or_create_product` 최우선 단계에 `external_id` 조회 로직을 추가하는 작업은 4단계가 아니라 **Phase 2(Shopify 스크래퍼 연동)와 반드시 동시에 배포**되어야 함.

---

### [지적 3] 상품 병합(`_merge_products`) 및 소프트 삭제 시 고아 행 방치

- **심각도**: **P0 (정합성 차단)**
- **근거**:
  - 코드: `backend/app/tasks/match_products.py:201-227` (`_merge_products`)
  - 모델: `backend/app/models/product.py:22` (`deleted_at`), `backend/app/models/product_match_candidate.py`
- **왜 문제인가 (구체적 실패 시나리오)**:
  1. Celery 태스크 `match_pending_products`는 미매칭 고아 상품(`orphan`)을 정본(`canonical`) 상품으로 병합함.
  2. 현재 `_merge_products` 코드는 다음과 같이 동작함:
     ```python
     orphan.deleted_at = func.now()
     # ...
     await db.execute(update(SaleEvent).where(SaleEvent.product_id == orphan.id).values(product_id=canonical.id))
     ```
  3. `platform_product_ids` 테이블에 대한 `UPDATE` 로직이 완전히 누락되어 있음.
  4. **결과**:
     - `orphan`이 소프트 삭제되어도 `platform_product_ids`는 삭제된 `orphan.id`를 계속 가리킴 (고아 매핑).
     - 다음 수집 시 스크래퍼가 해당 `external_id`로 조회하면 `deleted_at`이 찍힌 죽은 Product를 가져와서 되살리거나, `Product.deleted_at.is_(None)` 조건으로 인해 매칭에 실패하고 다시 신규 생성을 시도하다 UNIQUE 충돌을 냄.
  5. 또한 `orphan`의 `platform_product_ids`를 `canonical`로 이전하려 할 때, 만약 `canonical`에도 이미 동일한 `(platform_name, external_id)`가 존재한다면 단순 UPDATE 시 유니크 제약 위반이 발생하므로 충돌 처리(Merge/Delete)가 필요함.
- **수정 권고**:
  - `_merge_products` 함수에 `platform_product_ids` 소유권 이전 및 중복 삭제 로직 추가:
    ```python
    # orphan에 달린 platform_product_ids를 canonical로 이전 (중복 시 orphan 측 삭제)
    await db.execute(
        delete(PlatformProductId)
        .where(
            PlatformProductId.product_id == orphan.id,
            PlatformProductId.external_id.in_(
                select(PlatformProductId.external_id).where(PlatformProductId.product_id == canonical.id)
            )
        )
    )
    await db.execute(
        update(PlatformProductId)
        .where(PlatformProductId.product_id == orphan.id)
        .values(product_id=canonical.id)
    )
    ```

---

### [지적 4] Rakuten `itemCode`의 오픈마켓(셀러 종속) 특성 오판

- **심각도**: **P1 (머지 전 수정)**
- **근거**:
  - 문서 인용: `docs/design-platform-product-ids-2026-08-09.md` 36-41행 (`"itemCode": "shop123:10000456"`, "이 번호는 이름이 바뀌어도 안 바뀐다")
  - 코드: `backend/app/scrapers/jp/rakuten.py:28-51`
- **왜 문제인가 (구체적 실패 시나리오)**:
  1. Rakuten은 오픈마켓(Marketplace)이며 `itemCode`는 `shopCode:itemUrl` (상점ID:상점아이템ID) 구조임.
  2. 동일한 화장품(예: "타차 듀이 스킨 크림 50ml")이라도 공식몰(`tatcha:101`), 드럭스토어 A(`shopA:999`), 라쿠텐24(`rakuten24:555`) 등 **셀러마다 `itemCode`가 완전히 다름**.
  3. 셀러가 상품 페이지를 리뉴얼하거나 재등록하면 `itemCode`가 변경됨.
  4. 설계 문서의 주장처럼 "Rakuten itemCode 하나로 상품을 식별한다"고 가정하면:
     - 셀러 A의 리스팅을 수집해 `itemCode_A`를 저장했더라도, 다음번에 셀러 B의 최저가 리스팅을 수집하면 `itemCode_B`는 DB에 없으므로 기존 식별자 대조의 혜택을 전혀 받지 못함.
     - 수많은 셀러의 수만 개 `itemCode`가 단일 `Product`에 N:1로 매핑되어 테이블 행 수가 폭증함.
- **수정 권고**:
  - Rakuten의 `itemCode`는 "글로벌 정본 식별자"가 아니라 **"특정 상점의 리스팅 식별자"**임을 문서에 명시하고 한계를 규정할 것.
  - Rakuten의 경우 `itemCode` 외에 JAN 코드(일본 바코드, 13자리 숫자)가 API 응답에 제공되는지 확인하고, JAN 코드를 최우선 식별자로 채택할 것.

---

### [지적 5] Celery 동시 스크래핑 시 `ON CONFLICT` Upsert 부재

- **심각도**: **P1 (머지 전 수정)**
- **근거**:
  - 문서 인용: `docs/design-platform-product-ids-2026-08-09.md` 3절 (102-114행)
  - 코드: `backend/app/scrapers/collector.py:210-234` (`SaleEvent`의 `pg_insert ... on_conflict_do_nothing`)
- **왜 문제인가 (구체적 실패 시나리오)**:
  1. compa는 Celery 스윕 태스크 및 `asyncio.gather`를 통해 여러 플랫폼 스크래퍼를 병렬로 실행함.
  2. `SaleEvent` 테이블은 동시성 충돌을 방지하기 위해 `pg_insert(SaleEvent).values(...).on_conflict_do_nothing()`을 적용하고 있음.
  3. 하지만 `platform_product_ids` 테이블 생성 및 인서트 설계에는 `ON CONFLICT` 처리 방안이 누락되어 있음.
  4. 두 개 이상의 워커가 동일한 상품/플랫폼을 수집하거나 재시도할 때 `INSERT INTO platform_product_ids`를 동시에 실행하면 **경쟁 상태(Race Condition)로 인한 `UniqueViolation` 예외**가 발생하여 태스크가 실패함.
- **수정 권고**:
  - `platform_product_ids` 저장 로직에 PostgreSQL `pg_insert` + `on_conflict_do_nothing()` 또는 `on_conflict_do_update`를 필수로 적용할 것.

---

### [지적 6] Amazon ASIN 추출의 단순 정규식 의존 및 다중 파서 누락

- **심각도**: **P1 (머지 전 수정)**
- **근거**:
  - 문서 인용: `docs/design-platform-product-ids-2026-08-09.md` 90행, 150행 ("DetailPageURL 응답에서 /dp/ASIN코드 패턴으로 정규식 추출 가능", "정규식 하나 추가라 리스크 거의 없음")
  - 코드: `backend/app/scrapers/us/amazon.py:142-220` (`parse_paapi_response`), `backend/app/scrapers/us/amazon.py:231-316` (`parse_search_html`)
- **왜 문제인가 (구체적 실패 시나리오)**:
  1. `AmazonScraper`는 PA-API 모드와 HTML 스크래핑 폴백 모드의 2개 파이프라인을 가짐.
  2. **PA-API 모드**: API 응답 JSON의 `item` 객체에 `ASIN` 필드(`item["ASIN"]`)가 최상위에 직접 존재함. URL에서 정규식으로 파싱할 필요가 없음.
  3. **HTML 폴백 모드**:
     - HTML 검색 결과 컨테이너 `div[data-component-type="s-search-result"]`에는 `data-asin` 속성이 직접 존재함.
     - 반면 검색 결과의 `h2 a` 링크(`href`)는 스폰서 리디렉트 URL(`/gp/slredirect/...`, `/sspa/click?...`)이거나 상대 경로 파싱 실패 시 검색 페이지 URL(`https://www.amazon.com/s?k=...`)로 폴백됨 (`amazon.py:295`).
     - URL에서 `/dp/([A-Z0-9]{10})` 정규식만 추출하려 하면 스폰서 상품 및 폴백 URL에서 ASIN 추출 실패율이 급증함.
- **수정 권고**:
  - PA-API 파서에서는 `item.get("ASIN")`을 직접 읽고, HTML 파서에서는 `item.get("data-asin")` 속성을 1순위로 추출하도록 명세할 것.

---

### [지적 7] `platform_name` 문자열 비정규화 및 역방향 인덱스 누락

- **심각도**: **P2 (있으면 좋음)**
- **근거**:
  - 문서 인용: `docs/design-platform-product-ids-2026-08-09.md` 108행 (`platform_name: String`)
  - 코드: `backend/app/models/platform.py`, `backend/app/models/sale_event.py:21` (`platform_id: UUID FK`)
- **왜 문제인가**:
  1. 기존 `SaleEvent` 모델은 `platforms` 테이블의 `id`(UUID ForeignKey)를 참조하여 데이터 무결성을 유지함.
  2. 새 테이블만 `platform_name: String`을 사용하면 플랫폼명 변경 시 외래키 무결성이 깨지고, 스키마 일관성이 훼손됨.
  3. 또한 `(platform_name, external_id)` 복합 유니크 인덱스만 생성할 경우, `product_id`로 조회하는 역방향 쿼리(`SELECT * FROM platform_product_ids WHERE product_id = :id`) 실행 시 인덱스를 타지 못해 **테이블 풀스캔**이 발생함. (상품 병합, 상품 삭제, 관리자 조회 시 성능 저하).
- **수정 권고**:
  - `platform_id: UUID = ForeignKey("platforms.id")`를 사용하거나, `platform_name`을 유지하더라도 `ix_platform_product_ids_product_id` 인덱스를 반드시 생성할 것.

---

## 4. 감사가 놓친 것 (자체 발견 심층 결함)

감사 질문 목록에는 없었으나 실제 코드베이스를 전수 조사하여 발견한 3가지 심층 결함입니다.

---

### [자체 발견 1] [P0] 카탈로그 시딩(`catalog.py`)과의 충돌 및 데드락 위험

- **근거**: `backend/app/scrapers/catalog.py:40-65` (`seed_catalog`)
- **내용**:
  1. `seed_catalog` 함수는 Shopify 공홈 `products.json`을 스윕하여 `products` 테이블에 상품을 시딩함.
  2. 한 Shopify 상품의 여러 Variant(예: 30ml, 50ml)가 시딩 루프를 돌 때, `catalog.py`는 `event.product_name`으로 중복을 검사함.
  3. 만약 시딩 단계에서 `platform_product_ids`를 함께 삽입하도록 확장할 경우, Variant ID가 아닌 Product ID를 사용하면 시딩 도중 유니크 제약 위반으로 전체 시딩 프로세스가 중단됨.
  4. 시딩 로직에도 `platform_product_ids` 삽입 및 Variant 매핑 규칙이 명확히 정의되어야 함.

---

### [자체 발견 2] [P0] 관리자 수동 병합(`ProductMatchCandidate`) 승인 시 매핑 이전 누락

- **근거**: `backend/app/models/product_match_candidate.py:18-21`, `backend/app/api/admin.py`
- **내용**:
  1. compa는 자동 매칭 외에 `ProductMatchCandidate`를 통해 관리자가 수동으로 매칭을 승인(`approved`)하는 워크플로우를 가짐.
  2. 관리자가 승인 API를 호출할 때 `orphan_product_id`의 `platform_product_ids`를 `canonical_product_id`로 이전하지 않으면, 수동 검토를 거쳐 병합된 정본 상품에는 외부 식별자가 연결되지 않아 다음 스크래핑 때 다시 분리되는 버그가 발생함.

---

### [자체 발견 3] [P1] Rakuten 멀티 셀러 리스팅의 무제한 적재에 따른 테이블 오염

- **근거**: `backend/app/scrapers/jp/rakuten.py`, `backend/app/scrapers/collector.py`
- **내용**:
  1. Rakuten 검색 시 인기 상품(예: SK-II)은 수백 개 셀러의 리스팅이 반환됨.
  2. 모든 셀러의 `shopCode:itemCode`를 `platform_product_ids`에 영구 저장하면, 폐업하거나 상품을 내린 셀러의 더미 식별자가 수십만 건 누적되어 DB 인덱스 효율이 급격히 저하됨.
  3. 공홈/공식몰(`official`) 식별자 우선 적재 정책 또는 마지막 관측일(`last_seen_at`) 필드가 요구됨.

---

## 5. 수정 가이드라인 및 코드 패치 예시

설계 문서를 수정할 때 반영해야 할 권고 DDL 및 코드 구조입니다.

### A. 올바른 모델 및 스키마 정의 (`platform_product_id.py`)

```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class PlatformProductId(Base):
    __tablename__ = "platform_product_ids"
    __table_args__ = (
        UniqueConstraint("platform_id", "external_id", name="uq_platform_external_id"),
        Index("ix_platform_product_ids_product_id", "product_id"),
        Index("ix_platform_product_ids_lookup", "platform_id", "external_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    platform_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platforms.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    id_type: Mapped[str] = mapped_column(String(50), nullable=False, default="variant_id")  # variant_id, asin, jan, item_code
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

### B. `get_or_create_product` 연동 로직 (Phase 2에서 즉시 통합)

```python
async def find_by_external_id(
    db: AsyncSession, platform_id: uuid.UUID, external_id: str
) -> Product | None:
    """외부 식별자로 활성 상품 즉시 조회 (O(1) Fast-Path)."""
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
```

---

## 6. 최종 결론 및 권고

`design-platform-product-ids-2026-08-09.md` 문서는 **"식별자 우선 대조"**라는 훌륭한 아키텍처적 방향성을 제시하고 있으나, **(1) Shopify Variant 미분리, (2) 매처 수정 4단계 지연에 따른 런타임 크래시, (3) Celery 상품 병합 시 고아 행 방치**라는 3대 치명적 P0 결함을 안고 있습니다.

따라서 본 문서는 위 3대 P0 결함 및 P1 지적 사항들을 보완하여 설계를 개정한 후 구현(Codex 핸드오프)에 착수할 것을 권고합니다.
