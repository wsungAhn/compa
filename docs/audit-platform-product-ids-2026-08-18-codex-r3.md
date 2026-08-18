# platform_product_ids 설계 Codex 확인 감사 R3 — 2026-08-18

> **서열**: Codex 확인 라운드 R2(`audit-platform-product-ids-2026-08-18-codex-r2.md`)
> 이후 재확인 라운드.
> **대상 설계**: `docs/design-platform-product-ids-2026-08-09.md` v3
> **감사 기준**: R2가 요구한 5가지 수정이 v3에 실제 반영됐는지, 현재
> `backend/app/` 코드의 실제 함수 시그니처와 실행 경로에 맞는지 독립 검증.

## 판정 요약

| # | R2 요구 / 검증 항목 | R3 판정 | 구현 착수 영향 |
|---|---|---|---|
| 1 | 대상 파일에 `scrapers/base.py`, `collector.py` 추가 | **해결됨** | v3 상단 대상 파일에 둘 다 추가됨 |
| 2 | `ScrapedEvent` 필드 및 collector 저장 흐름이 실제 시그니처와 정합 | **부분해결** | 필드/함수 위치는 맞지만 authoritative `product_id` 반환값을 `SaleEvent` 저장에 쓰는 순서가 닫히지 않음 |
| 3 | fast-path 위치: `_collect_platform`의 `get_or_create_product` 직전 | **부분해결** | on-demand 수집 경로에서는 실행 가능. 단, 브랜드 catalog sweep 경로(`tasks/collect.py:_collect_all`)는 여전히 빠짐 |
| 4 | upsert 충돌 정책: `RETURNING`으로 기존 `product_id` 반환, 조용한 재귀속 방지 | **부분해결** | SQLAlchemy/PostgreSQL API 형태는 맞음. 하지만 `persist_events_for_product` 삽입 순서와 연결되지 않아 동작 계약 미완성 |
| 5 | 2절 표의 Shopify 서술을 `variant.id` 기준으로 정정 | **해결됨** | 2절 표는 `variants[].id` 기준으로 정정됨. 단, 1절 예시/2절 결론에 `handle` 잔재가 남음 |

## 상세

### 1. 대상 파일 목록 — 해결됨

v3 상단 대상 파일 목록은 R2가 요구한 파일을 포함한다.

- `backend/app/scrapers/base.py`: `ScrapedEvent`에 `external_id`/`id_type` 필드 추가 대상으로 명시.
- `backend/app/scrapers/collector.py`: `_collect_platform` fast-path 및 `persist_events_for_product` upsert 대상으로 명시.

현재 실제 코드도 이 판단과 맞다. `ScrapedEvent`는 `backend/app/scrapers/base.py:32`의
dataclass이고, 현재 필드는 `size_ml`까지만 있어 새 필드 추가가 필요하다.
collector의 실제 경계도 `group_events_by_product_name`(`collector.py:186`),
`persist_events_for_product`(`collector.py:197`), `_collect_platform`(`collector.py:261`)로
존재한다.

### 2. `ScrapedEvent`/collector 흐름 — 부분해결

v3는 실제 코드 시그니처를 대체로 정확히 읽었다.

- `group_events_by_product_name(events: list[ScrapedEvent]) -> dict[str, list[ScrapedEvent]]`
  는 이름별 그룹만 만든다.
- `persist_events_for_product(db, product, platform, scraped) -> int`는 이벤트별로
  `SaleEvent`를 insert하고 마지막에 commit한다.
- `_collect_platform(...)`은 그룹당 한 번 `get_or_create_product(db, product_name, brand,
  platform_country)`를 호출한 뒤, 같은 그룹 전체를 `persist_events_for_product`에 넘긴다.

하지만 v3 5-3절의 핵심 계약과 4절의 삽입 위치가 아직 완전히 맞물리지 않는다.
5-3절은 `upsert_platform_product_id(...) -> uuid.UUID`가 authoritative `product_id`를
반환하고, 호출자가 그 반환값을 실제 저장에 써야 한다고 말한다. 그런데 4절 4번은
upsert 위치를 "`persist_events_for_product`, 이벤트별 `SaleEvent` insert와 같은 루프 안"으로만
적고, 실제 `SaleEvent` insert 전에 upsert를 호출해 반환 `product_id`를 쓰는지 명시하지 않는다.

이 순서가 중요하다. 현재 `persist_events_for_product`는 `product.id`로 `SaleEvent`를
insert한다(`collector.py:210~230`). 만약 upsert가 conflict에서 기존 P1을 반환했는데
이미 P2로 `SaleEvent`를 insert한 뒤라면, "기존 매핑이 authoritative"라는 정책이 이벤트
저장에는 적용되지 않는다. v3 5-3절의 "새 P2는 빈 고아로 자연 정리"라는 설명도 이 경우
성립하지 않는다. P2에 방금 `SaleEvent`가 생겼기 때문이다.

수정 필요: `persist_events_for_product` 안의 이벤트별 루프에서 `s.external_id`가 있으면
`SaleEvent` insert 전에 upsert를 먼저 호출하고, 반환된 `authoritative_product_id`를
`SaleEvent.product_id`에 사용한다고 명시해야 한다. 반환값이 입력 `product.id`와 다르면
가능하면 `Product` 객체 재조회 없이 UUID만 insert에 쓰거나, logging/metric을 남겨야 한다.

### 3. fast-path 위치 — 부분해결

v3가 지정한 `_collect_platform`의 `get_or_create_product` 호출 직전 위치는 실제로 존재하고
실행 가능하다. 현재 코드는 `collector.py:307~310`에서 그룹별로 brand를 뽑고,
바로 `get_or_create_product`를 호출한다. 이 직전에 그룹 이벤트의 external id를 검사해
`find_by_external_id`를 먼저 호출하는 설계는 on-demand 수집 경로에서는 맞다.

다만 같은 Shopify `ScrapedEvent`를 처리하는 다른 경로가 빠졌다. `backend/app/tasks/collect.py:_collect_all`
은 브랜드 공홈 카탈로그 sweep에서 `group_events_by_product_name` 후
`find_exact_for_sweep`만 호출하고(`tasks/collect.py:60~67`), `_collect_platform`을 거치지 않는다.
상품명이 바뀌면 여기서는 external id fast-path가 있어도 사용되지 않고 `skipped_groups`로 빠진다.

수정 필요: fast-path helper를 `_collect_platform` 전용으로 두지 말고, 브랜드 sweep도 같은
resolver를 쓰도록 명시해야 한다. 최소 설계는 `resolve_product_for_events(db, platform,
events, fallback)` 같은 공용 helper를 만들고 `_collect_platform`과 `_collect_all`이 같이 쓰는
방식이다. 또는 `persist_events_for_product`가 authoritative `product_id`를 insert 전에
반영하도록 강제하되, sweep의 `product is None`인 그룹도 external id로 product를 찾을 수 있게
별도 분기를 추가해야 한다.

### 4. upsert 충돌 정책 — 부분해결

v3 5-3절의 SQLAlchemy API 사용 형태 자체는 PostgreSQL upsert 정책과 맞다.

```python
pg_insert(PlatformProductId).values(...).on_conflict_do_update(
    index_elements=["platform_id", "external_id"],
    set_={"last_seen_at": func.now()},
).returning(PlatformProductId.product_id)
```

PostgreSQL에서는 `ON CONFLICT DO UPDATE ... RETURNING product_id`가 insert된 행 또는
conflict로 update된 기존 행의 `product_id`를 반환한다. `set_`에서 `product_id`를 제외하면
기존 매핑의 `product_id`가 유지되므로, "조용한 재귀속 방지" 정책 자체는 성립한다.

로컬 검증 한계: 현재 세션의 시스템 `python3`에는 SQLAlchemy가 설치되어 있지 않아
PostgreSQL dialect 컴파일 실행은 하지 못했다(`ModuleNotFoundError: No module named
'sqlalchemy'`). 따라서 여기서는 프로젝트의 `requirements.txt`가 지정한 SQLAlchemy 2.0.35
API 형태와 정적 코드 대조로 판정했다.

남은 문제는 SQL 문법이 아니라 호출 계약이다. 5-3절은 반환값을 실제 저장에 쓰라고
말하지만, 4절은 그 반환값을 `SaleEvent` insert 전에 쓰도록 고정하지 않는다. 이 때문에
R2의 "기존 product_id 반환, 조용한 재귀속 방지" 요구는 정책 문장 수준에서는 반영됐지만,
현재 collector 함수 구조 안에서 안전하게 실행되는 설계로는 아직 닫히지 않았다.

### 5. Shopify `variant.id` 정정 — 해결됨, 잔재 있음

2절 선행조사 표의 Shopify 행은 `variants[].id` 기준으로 고쳐졌다. `handle`도 가변 URL
slug라 식별자로 미채택한다고 정리되어 있어 R2 요구의 핵심은 해결됐다.

단, v3 1절 예시는 아직 `products.json` 최상위 `id`와 `handle`을 "고유 번호/별칭"이라고
설명한다. 2절 결론에도 "itemCode/ASIN/handle"을 저장한다고 남아 있다. 이 잔재는 구현
계약을 직접 깨지는 않지만, 설계 문서를 처음 읽는 구현자에게 Shopify 식별자 레벨을 다시
헷갈리게 만들 수 있다.

수정 권장: 1절 Shopify 예시를 `variants: [{"id": ...}]` 중심으로 바꾸고, 2절 결론의
`handle`을 `variant.id`로 정정한다.

## 신규 발견 문제

### [P1] 브랜드 catalog sweep 경로가 fast-path 설계에서 빠졌다

`_collect_platform`만 고치면 `collect_on_demand` 계열은 해결되지만, Celery의
`collect_all_products`는 `backend/app/tasks/collect.py:_collect_all`에서 별도 흐름으로
Shopify 브랜드 카탈로그를 훑는다. 이 경로는 `find_exact_for_sweep` 실패 시 저장 자체를
건너뛰므로, external id가 있어도 renamed product를 복구하지 못한다.

권장: product resolver를 collector 공용 helper로 만들고 `_collect_platform`과 `_collect_all`이
같이 쓰게 한다. 이 helper는 "신뢰 가능한 external id면 fast-path, Rakuten item_code면 제외,
없으면 기존 이름 매칭" 순서를 한 곳에서 강제해야 한다.

### [P1] authoritative `product_id` 반환값을 `SaleEvent` insert 전에 쓰는 순서가 명시되지 않았다

upsert helper가 기존 `product_id`를 반환해도, 현재 `persist_events_for_product` 구조에서는
잘못된 `product.id`로 먼저 `SaleEvent`가 insert될 수 있다. 이 경우 v3가 기대한 "P2는 빈
고아로 자연 정리"가 아니라 "P2에 이벤트가 붙은 중복 상품"이 된다.

권장: `persist_events_for_product`의 루프 순서를 명시한다.

1. event confidence 확인.
2. external id가 있으면 upsert 먼저 호출.
3. 반환된 authoritative `product_id`를 `SaleEvent.product_id`로 사용.
4. external id가 없으면 기존 `product.id` 사용.
5. 반환값이 입력 product와 다를 때 warning 로그 및 테스트 추가.

### [P2] 스키마 예시의 `last_seen_at` 설명이 아직 `onupdate` 중심이다

R2가 지적한 `onupdate=func.now()` 표현이 3절 테이블 설명에 남아 있다. v3 5-3절 예시는
`set_={"last_seen_at": func.now()}`를 직접 넣어 맞지만, 컬럼 표만 읽으면 bulk upsert에서도
ORM `onupdate`가 자동 적용된다고 오해할 수 있다.

수정 권장: `last_seen_at` 설명을 "server_default + upsert `set_`에서 직접 갱신"으로 바꾼다.

## Act-Based Verification

서비스 실행은 하지 않았다. 이번 라운드는 설계 문서와 실제 코드 시그니처/흐름 대조가
목적이며, 아직 구현 코드가 없기 때문이다.

실행 확인:

- `backend/app/scrapers/base.py`, `collector.py`, `brands/shopify.py`, `tasks/collect.py`,
  `scrapers/catalog.py`, `tasks/match_products.py`, `api/admin.py`를 줄번호 기준으로 확인.
- `python3`로 SQLAlchemy PostgreSQL dialect 컴파일을 시도했으나 로컬 모듈 미설치로 실패.
  따라서 SQL 문법 판정은 SQLAlchemy 2.0 API 형태의 정적 검증으로 제한했다.

## 최종 결론

**NEEDS_REVISION**

R2의 5개 요구는 문서 표면상 대부분 반영됐다. 특히 대상 파일 누락, `ScrapedEvent`
필드 추가, `_collect_platform` fast-path 위치, Shopify 2절 표 정정, upsert의 "기존
product_id 유지 + RETURNING" 정책은 방향이 맞다.

하지만 구현 착수 전 아래 3가지는 v3에 더 반영해야 한다.

1. `persist_events_for_product`에서 upsert 반환 `product_id`를 `SaleEvent` insert 전에
   사용하도록 순서를 명시.
2. `_collect_platform`뿐 아니라 `tasks/collect.py:_collect_all` 브랜드 catalog sweep도
   같은 external id fast-path/resolver를 쓰도록 대상 파일과 구현 흐름에 추가.
3. 1절 Shopify 예시와 2절 결론의 `product.id`/`handle` 잔재, 3절 `last_seen_at onupdate`
   표현을 정리.

1~2번은 동작 정합성 문제라 구현 착수 게이트다. 3번은 문서 혼선 방지용이지만 같이 고치는
편이 안전하다.
