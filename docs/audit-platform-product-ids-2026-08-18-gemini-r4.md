# platform_product_ids 설계 적대적 감사 보고서 R4 — 2026-08-18

> **서열 및 목적**: 본 감사는 Codex 2회 연속 감사(R2, R3) 이후 동일 감사자의 사각지대를 방지하기 위해 감사자를 전환하여 수행하는 **4차 확정 적대적 감사(R4)**다.
> **감사 대상 문서**: `docs/design-platform-product-ids-2026-08-09.md` (v4 개정판, 커밋 `fb2ea6d`)
> **감사자**: Gemini / Antigravity (독점 감사 세션)
> **감사 기준**: 실제 백엔드 소스코드(`backend/app/` 하위 스크래퍼, 태스크, 모델, AI 매처)와의 함수 시그니처·트랜잭션 실행 흐름·예외 경로 대조 및 런타임 무결성 검증

---

## 1. 판정 요약

| # | 지적 / 검증 항목 | v4 상태 | R4 판정 | 심각도 | 핵심 이유 |
|---|---|---|---|---|---|
| **1** | **공용 helper(`resolve_product_by_external_id`) 재사용성** | v4 신규 도입 | **부분수용** | **P1** | `_collect_platform`과 `_collect_all` 양쪽에서 재사용 가능한 구조이나, Rakuten `item_code` 제외 필터링과 다중 Variant 순회 계약이 helper 수준에서 명시되지 않음 |
| **2** | **`persist_events_for_product` 순서 변경 및 트랜잭션 안전성** | v4 반영 완료 | **수용** | **-** | `upsert` 선행 호출 후 반환된 authoritative `product_id`로 `SaleEvent`를 저장하는 순서가 단일 `AsyncSession` 트랜잭션 및 다중 variant 루프에서 완전하게 안전함을 확인 |
| **3** | **Rakuten / Amazon 스크래퍼 (Phase 3) 구체성** | 3단계 요약 기술 | **부분수용** | **P2** | Amazon(PA-API `ASIN`, HTML `data-asin`)은 구체적이나, Rakuten의 경우 `itemCode` 추출 키 및 fast-path 제외 로직의 스크래퍼-helper 간 연결 규정이 다소 축약됨 |
| **4** | **`matcher.py` Phase 2 통합 및 LLM 스킵 메커니즘** | Phase 2 동시 배포 | **수용** | **-** | `collector.py`와 `tasks/collect.py` 계층에서 `get_or_create_product` 호출을 사전에 가로채므로 O(1) DB 조회를 통해 `find_matching_product` 및 Claude LLM 호출이 완벽히 스킵됨 |
| **5** | **[자체발견 1] 소프트 삭제(`deleted_at`)와 upsert 간의 비대칭 (유령 상품 루프)** | **v4 미반영 (신규)** | **반려** | **P0** | `find_by_external_id`는 삭제된 Product를 무시하나, `upsert_platform_product_id`는 삭제된 Product의 `product_id`를 그대로 반환하여 **삭제된 상품에 `SaleEvent`가 매일 부착되고 신규 상품이 매일 고아로 생성되는 무한 루프** 발생 |
| **6** | **[자체발견 2] `_collect_platform` 반환값(`collected_product_ids`) 재귀속 불일치** | **v4 미반영 (신규)** | **부분수용** | **P2** | `persist_events_for_product`에서 이벤트가 다른 기존 상품으로 재귀속될 때, `_collect_platform`이 반환하는 ID 집합과 실제 이벤트가 들어간 상품 ID 간의 불일치 발생 |
| **7** | **[자체발견 3] `_match_pending_products`의 고아 정리 대상 서술 오류** | v4 5-3절 서술 | **수용 권고** | **P2** | v4 5-3절은 "P2가 `_match_pending_products`에서 정리된다"고 기술하나, 실제 코드는 `name_en IS NULL`인 일본 고아만 스캔하므로 Shopify(US) 상품은 스캔 대상이 아님 |

---

## 2. 설계에서 타당하게 개선·수렴된 부분 (정당한 결정)

1. **R3 지적 1 완전 해소: `persist_events_for_product` 내 `upsert` 선행 호출 및 Authoritative `product_id` 강제**
   - **근거**: v4 4절 4번, 5-3절 `upsert_platform_product_id`
   - **평가**: 함수 인자로 전달된 `product.id`를 무조건 신뢰하지 않고, PostgreSQL `ON CONFLICT DO UPDATE ... RETURNING product_id`를 통해 반환된 식별자를 `SaleEvent.product_id`에 바인딩하도록 순서를 고정함. 이를 통해 다중 Variant가 서로 다른 정본에 매핑되어 있거나 이름 매칭이 어긋났을 때도 이벤트가 올바른 정본으로 귀속됨.

2. **R3 지적 2 완전 해소: `tasks/collect.py:_collect_all` 브랜드 스윕 fast-path 통합**
   - **근거**: v4 4절 5번
   - **평가**: 일일 수집의 실제 주력 경로인 `_collect_all`에서 `find_exact_for_sweep` 호출 전에 external_id fast-path를 배치하여, 브랜드 리브랜딩이나 시즌명 변경 시에도 식별자 기반으로 연속 갱신되도록 수렴함.

3. **문서 잔재 정리 및 식별자 레벨 통일**
   - **근거**: v4 1절, 2절, 3-1절
   - **평가**: Shopify 식별자가 `variant.id`임을 명확히 하고, `handle` 및 `product.id` 잔재를 걷어냄. `last_seen_at` 역시 ORM `onupdate`가 아닌 upsert의 `set_` 절에서 명시적으로 갱신함을 기술하여 혼선을 제거함.

---

## 3. 5대 핵심 질문에 대한 심층 검증

---

### [검증 1] 공용 helper (`resolve_product_by_external_id`)의 `_collect_platform` 및 `_collect_all` 재사용성

- **판정**: **부분수용 (P1 — 계약 명세 보완 필요)**
- **실제 코드 대조**:
  - `backend/app/scrapers/collector.py:307-311` (`_collect_platform`):
    ```python
    for product_name, events in by_product.items():
        brand = events[0].brand if events else None
        # [Fast-path 삽입 지점]
        prod = await get_or_create_product(db, product_name, brand, platform_country)
        await persist_events_for_product(db, prod, platform, events)
    ```
  - `backend/app/tasks/collect.py:60-65` (`_collect_all`):
    ```python
    for product_name, group in group_events_by_product_name(events).items():
        # [Fast-path 삽입 지점]
        product = await find_exact_for_sweep(db, product_name, ScraperClass.BRAND)
        if product is None:
            skipped_groups += 1
            continue
    ```
- **검증 분석**:
  1. **호출 컨텍스트 정합성**: 두 호출부 모두 `(db, platform, events: list[ScrapedEvent])`를 가지고 있으며, 반환받고자 하는 대상은 `Product | None`이다. 따라서 공용 helper의 시그니처를 `resolve_product_by_external_id(db: AsyncSession, platform_id: uuid.UUID, events: list[ScrapedEvent]) -> Product | None`로 정의하면 두 곳 모두 완벽히 호환된다.
  2. **helper 내부 순회 로직의 필요성**: 한 상품의 이벤트 그룹(`events`)에는 여러 Variant(예: 50ml id `40111`, 100ml id `40222`)가 들어있다. 만약 50ml가 신규 Variant이고 100ml가 기존에 등록된 Variant라면, `events[0]`만 검사해서는 매칭에 실패한다. 따라서 helper는 `events` 내의 모든 `s.external_id`를 순회하며 `find_by_external_id`를 시도하고 첫 번째 발견된 `Product`를 반환해야 한다.
  3. **Rakuten `item_code` 배제 정책의 강제**: v4 3-2절에 따라 Rakuten `item_code`는 fast-path에서 제외되어야 한다. helper 내부에서 `if s.id_type == "item_code": continue` 처리를 해주지 않으면 호출부마다 중복 필터링을 작성해야 하는 drift 위험이 있다.
- **개선 요구사항**:
  - `resolve_product_by_external_id`의 정확한 시그니처와 내부 동작(다중 이벤트 순회 + `id_type != "item_code"` 검사)을 문서 5-3절에 코드 수준으로 명시할 것.

---

### [검증 2] `persist_events_for_product` 순서 변경 및 트랜잭션/세션 안전성

- **판정**: **수용 (완전 안전)**
- **실제 코드 대조**:
  - `backend/app/scrapers/collector.py:197-234`
- **검증 분석**:
  1. **SQL 실행 및 Flush 타이밍**:
     - `await db.execute(stmt_upsert)` 호출 시 SQLAlchemy는 PostgreSQL로 즉시 `INSERT ... ON CONFLICT DO UPDATE ... RETURNING product_id`를 전송한다.
     - `result.scalar_one()`은 DB가 확정한 `authoritative_product_id`를 즉시 반환한다.
     - 이어서 실행되는 `stmt_sale_event = pg_insert(SaleEvent).values(product_id=authoritative_product_id, ...)`는 앞서 확정된 UUID를 외래키로 사용하여 안전하게 삽입된다.
  2. **단일 세션 내 다중 Upsert 안전성**:
     - 그룹 내 Variant 1(50ml), Variant 2(100ml)가 순차적으로 루프를 돌 때, 하나의 세션 안에서 독립된 두 번의 upsert와 두 번의 `SaleEvent` insert가 실행되고 루프 종료 후 `await db.commit()`이 단 1회 실행된다.
     - PostgreSQL MVCC 및 Row-level Lock 메커니즘상 동일 트랜잭션 내에서 서로 다른 `external_id`의 upsert가 충돌하거나 데드락을 유발할 위험이 전혀 없다.
  3. **동일 `external_id` 중복 유입 시**:
     - 동일 배치 내에 같은 `external_id`를 가진 이벤트가 중복으로 들어오더라도, 첫 번째는 INSERT되고 두 번째는 `ON CONFLICT DO UPDATE`로 처리되어 동일한 `product_id`를 반환하므로 안전하다.

---

### [검증 3] Rakuten / Amazon 스크래퍼 (Phase 3)의 구체성 및 모호성

- **판정**: **부분수용 (P2 — 파서별 매핑 명시 권고)**
- **실제 코드 대조**:
  - `backend/app/scrapers/jp/rakuten.py:28-51` (`parse_response`)
  - `backend/app/scrapers/us/amazon.py:142-220` (`parse_paapi_response`), `231-316` (`parse_search_html`)
- **검증 분석**:
  1. **Amazon 스크래퍼**:
     - PA-API 파서: `item.get("ASIN")` -> `external_id=asin, id_type="asin"`
     - HTML 파서: `item.get("data-asin")` -> `external_id=asin, id_type="asin"`
     - 3-3절에 구체적으로 명시되어 있어 구현자가 혼선 없이 작성 가능함.
  2. **Rakuten 스크래퍼**:
     - `parse_response`에서 `item.get("itemCode")` 추출 -> `external_id=itemCode, id_type="item_code"`
     - 3-2절과 4절 3단계에 서술되어 있으나, `rakuten.py`의 파싱 루프 안에서 `item.get("itemCode")` 필드명을 직접 지정하는 형태의 예시가 빠져 있음.
- **개선 권고**:
  - `rakuten.py` 파서에서 `item.get("itemCode")`를 추출한다는 점을 4절 3단계에 한 줄 명시하면 3단계 구현 시 완전 무결함.

---

### [검증 4] `matcher.py` Phase 2 통합 및 LLM 스킵 메커니즘 상호작용

- **판정**: **수용 (구조적 타당성 확인)**
- **실제 코드 대조**:
  - `backend/app/ai/matcher.py:112-209` (`find_matching_product`), `294-347` (`get_or_create_product`)
  - `backend/app/ai/pipeline.py:168`
- **검증 분석**:
  1. **LLM 호출 스킵의 실현 방식**:
     - `_collect_platform` 및 `_collect_all` 계층에서 `resolve_product_by_external_id`를 먼저 실행하여 `Product`를 확보하면, `get_or_create_product` 자체가 호출되지 않는다.
     - 따라서 `find_matching_product`의 3단계(`_ask_claude_for_match`) 및 정규화/DB 쿼리가 완전히 바이패스되어 O(1) 매칭이 실현된다.
  2. **`matcher.py` 변경 불필요성 (설계적 우수성)**:
     - fast-path를 `matcher.py`의 `get_or_create_product` 내부가 아니라 호출 계층(`collector.py`, `tasks/collect.py`)에 둠으로써, `matcher.py`는 순수한 "이름 기반 매칭기"로서의 단일 책임을 유지할 수 있다.
     - 또한 `pipeline.py`(SNS 게시글 이벤트 추출 등 external_id가 없는 소스)와 같은 다른 호출처의 시그니처를 깨뜨리지 않는다.
  3. **문서 서술 정합성**:
     - v4 상단 대상 파일에 `backend/app/ai/matcher.py`가 적혀 있으나, 실제로는 `matcher.py` 내부를 수정하는 것이 아니라 `matcher` 호출을 우회하는 것이므로, 구현 시 `matcher.py`는 수정하지 않거나 `find_by_external_id` helper의 위치로만 활용할 수 있다.

---

## 4. 감사가 놓친 것 (신규 발견 결함 — Codex 사각지대)

---

### [자체발견 1] [P0] 소프트 삭제(`deleted_at`)와 `upsert_platform_product_id` 간의 비대칭 결함 (유령 상품 무한 루프)

- **심각도**: **P0 (치명적 런타임 정합성 결함)**
- **근거 코드**:
  - `backend/app/models/product.py:22` (`deleted_at`)
  - `docs/design-platform-product-ids-2026-08-09.md` 5-3절 (`find_by_external_id`, `upsert_platform_product_id`)
- **실패 시나리오 (치명적 버그 재현 흐름)**:
  1. 관리자나 병합 로직, 또는 기타 사유로 특정 상품 $P_{old}$가 소프트 삭제됨 (`$P_{old}.deleted_at = \text{now()}$`).
  2. $P_{old}$에 연결되어 있던 `platform_product_ids` 행 `(platform_id, "ext_123") -> P_{old}`는 DB에 그대로 남아있음.
  3. **1일차 수집 실행**:
     - `find_by_external_id` 실행: `Product.deleted_at.is_(None)` 조건 때문에 삭제된 $P_{old}$를 무시하고 **`None` 반환**!
     - fast-path가 실패했으므로 `get_or_create_product`로 폴백 -> 이름 매칭도 실패하여 **새로운 상품 $P_{new1}$ 생성** 및 flush.
     - `persist_events_for_product` 진입 -> `upsert_platform_product_id(db, P_{new1}.id, platform_id, "ext_123", ...)` 호출.
     - PostgreSQL에서 `ON CONFLICT (platform_id, external_id)` 발생!
     - `set_={"last_seen_at": func.now()}`만 실행되고 `product_id`는 갱신되지 않으므로, `RETURNING product_id`는 **삭제된 $P_{old}.id$를 반환**!
     - `SaleEvent`는 반환받은 **삭제된 상품 $P_{old}.id$로 저장됨**.
     - 새로 만든 $P_{new1}$은 이벤트가 0개인 빈 고아로 남음.
  4. **2일차 수집 실행**:
     - `find_by_external_id`는 여전히 $P_{old}$가 삭제 상태이므로 **`None` 반환**.
     - 또다시 **새로운 상품 $P_{new2}$ 생성**.
     - `upsert`는 또다시 **삭제된 $P_{old}.id$ 반환**.
     - `SaleEvent`는 또다시 **삭제된 $P_{old}$에 부착**.
  5. **결과**:
     - 스크래퍼가 돌 때마다 **새로운 빈 Product가 매일 무한 생성**됨.
     - 수집된 `SaleEvent`는 **삭제된 유령 상품에 계속 누적**되어 사용자 UI(가격 비교, 최저가 조회 등)에 영원히 노출되지 않음.
- **원인 분석**:
  - 읽기 경로(`find_by_external_id`)는 `deleted_at IS NULL`인 활성 상품만 인정하는데, 쓰기 경로(`upsert_platform_product_id`)는 `deleted_at` 여부를 확인하지 않고 기존 매핑의 `product_id`를 무조건 신뢰하기 때문임.
- **수정 권고**:
  - `upsert_platform_product_id`에서 conflict 발생 시, 기존 매핑의 `product_id`가 가리키는 `Product`가 이미 `deleted_at IS NOT NULL` 상태라면 **새로 전달된 `product_id`로 소유권을 재할당(UPDATE)** 하도록 수정해야 함.

```python
# 수정 권고: PostgreSQL conditional update 또는 사전 검증
async def upsert_platform_product_id(
    db: AsyncSession, product_id: uuid.UUID, platform_id: uuid.UUID, external_id: str, id_type: str
) -> uuid.UUID:
    """소프트 삭제를 고려한 매핑 upsert."""
    # 1. 기존 매핑이 활성 상품인지 조회
    existing = await db.execute(
        select(PlatformProductId.product_id, Product.deleted_at)
        .join(Product, Product.id == PlatformProductId.product_id)
        .where(
            PlatformProductId.platform_id == platform_id,
            PlatformProductId.external_id == external_id,
        )
    )
    row = existing.first()
    if row:
        existing_pid, deleted_at = row
        if deleted_at is None:
            # 기존 활성 상품 유지 (last_seen_at만 갱신)
            await db.execute(
                update(PlatformProductId)
                .where(PlatformProductId.platform_id == platform_id, PlatformProductId.external_id == external_id)
                .values(last_seen_at=func.now())
            )
            return existing_pid
        else:
            # 삭제된 상품의 매핑이면 새 활성 상품으로 재할당
            await db.execute(
                update(PlatformProductId)
                .where(PlatformProductId.platform_id == platform_id, PlatformProductId.external_id == external_id)
                .values(product_id=product_id, last_seen_at=func.now())
            )
            return product_id

    # 2. 신규 삽입
    stmt = pg_insert(PlatformProductId).values(
        product_id=product_id, platform_id=platform_id,
        external_id=external_id, id_type=id_type,
    ).on_conflict_do_update(
        index_elements=["platform_id", "external_id"],
        set_={"last_seen_at": func.now()},
    ).returning(PlatformProductId.product_id)
    result = await db.execute(stmt)
    return result.scalar_one()
```

---

### [자체발견 2] [P2] `_collect_platform` 반환값(`collected_product_ids`)의 재귀속 불일치

- **근거**: `backend/app/scrapers/collector.py:307-316`
- **내용**:
  - `_collect_platform`은 `prod = await get_or_create_product(...)`를 호출하고 `collected_product_ids.add(prod.id)`를 수행함.
  - 하지만 `persist_events_for_product` 내부에서 `upsert`에 의해 이벤트가 기존의 다른 `authoritative_product_id`로 재귀속되면, 실제 이벤트가 들어간 상품 ID와 `collected_product_ids`에 담긴 ID가 불일치하게 됨.
  - 이로 인해 `collect_on_demand`의 `_products_with_events(db, product_ids)` 결과에서 방금 수집된 이벤트가 누락될 수 있음.
- **수정 권고**:
  - `persist_events_for_product`가 실제로 이벤트가 바인딩된 `set[uuid.UUID]`를 반환하도록 하거나, `_collect_platform`에서 반환된 ID 집합을 `collected_product_ids`에 합산할 것.

---

### [자체발견 3] [P2] `_match_pending_products`의 고아 정리 대상 서술 오류

- **근거**: `docs/design-platform-product-ids-2026-08-09.md` 5-3절, `backend/app/tasks/match_products.py:238-244`
- **내용**:
  - v4 5-3절은 "새로 만들어진 P2가 이 이벤트 때문에 생성됐을 뿐이라면 다음 배치 정리(`_match_pending_products`)에서 빈 고아로 자연 정리된다"고 서술함.
  - 그러나 실제 `_match_pending_products` 쿼리는 `where(Product.name_en.is_(None), Product.name_jp.isnot(None))`로 **일본 플랫폼에서 수집된 영문명 없는 상품**만 대상으로 함.
  - Shopify나 Amazon 등 미국 플랫폼에서 생성된 P2는 `name_en`이 채워져 있으므로 `_match_pending_products`에 의해 스캔되지 않음.
  - (이벤트가 0개인 상품은 `_products_with_events`에 의해 UI 노출이 차단되므로 심각한 장애는 아니나, 설계 문서의 설명이 실제 코드 동작과 다르므로 바로잡아야 함).

---

## 5. 수정 가이드라인 및 코드 패치 명세

구현자가 즉시 참조할 수 있는 확정 코드 명세입니다.

### A. 공용 식별자 리졸버 (`resolve_product_by_external_id`)

```python
async def resolve_product_by_external_id(
    db: AsyncSession,
    platform_id: uuid.UUID,
    events: list[ScrapedEvent],
) -> Product | None:
    """이벤트 그룹 내의 external_id를 순회하여 기존 활성 상품을 조회 (O(1) Fast-Path).
    
    - Rakuten item_code 등 신뢰 불가 식별자는 제외.
    - 활성 상품(deleted_at IS NULL)이 발견되면 즉시 반환.
    """
    for s in events:
        if not s.external_id or s.id_type == "item_code":
            continue
        prod = await find_by_external_id(db, platform_id, s.external_id)
        if prod is not None:
            return prod
    return None
```

### B. `_collect_platform` 및 `_collect_all` 적용 구조

```python
# 1. collector.py:_collect_platform
for product_name, events in by_product.items():
    prod = await resolve_product_by_external_id(db, platform.id, events)
    if prod is None:
        brand = events[0].brand if events else None
        prod = await get_or_create_product(db, product_name, brand, platform_country)
    
    updated_pids = await persist_events_for_product(db, prod, platform, events)
    collected_product_ids.update(updated_pids)

# 2. tasks/collect.py:_collect_all
for product_name, group in group_events_by_product_name(events).items():
    product = await resolve_product_by_external_id(db, platform.id, group)
    if product is None:
        product = await find_exact_for_sweep(db, product_name, ScraperClass.BRAND)
    if product is None:
        skipped_groups += 1
        continue
    # ... persist_events_for_product 호출 ...
```

---

## 6. 최종 결론

**NEEDS_REVISION (1개 P0 결함 보완 후 즉시 구현 착수 가능)**

v4 설계 문서는 R1~R3 라운드를 거치며 식별자 레벨(`variant.id`), Celery 동시성, `_collect_all` 스윕 fast-path, `persist_events_for_product` 순서 고정 등 핵심 아키텍처를 대단히 완성도 높게 수렴시켰습니다.

그러나 R4 감사에서 새로 발견된 **[자체발견 1] 소프트 삭제 상품과 upsert 간의 비대칭 결함(P0)**은, 삭제된 상품이 존재할 때 스크래퍼가 매일 무한히 새 고아 Product를 생성하고 이벤트를 삭제된 상품에 잘못 부착하는 심각한 런타임 누수를 유발합니다.

따라서 아래 **2가지 항목만 v4 문서에 보완 반영(v5)**하면 즉시 완벽한 구현 착수가 가능합니다:

1. **[P0] `upsert_platform_product_id`의 소프트 삭제 대응 정책 추가**: conflict 대상이 `deleted_at IS NOT NULL`인 경우 새 `product_id`로 소유권을 재할당하는 로직 명세.
2. **[P1] 공용 helper `resolve_product_by_external_id`의 완전한 시그니처 및 `item_code` 제외/순회 계약 명시**.

위 2건 반영 후 추가 감사 라운드 없이 곧바로 코드 구현으로 진입할 것을 권고합니다.
