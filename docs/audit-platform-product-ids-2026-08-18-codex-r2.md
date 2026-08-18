# platform_product_ids 설계 Codex 확인 감사 R2 — 2026-08-18

> **서열**: 예비 감사 R1(`audit-platform-product-ids-2026-08-18-gemini-r1.md`) 이후
> 최종 확정 확인 라운드.
> **대상 설계**: `docs/design-platform-product-ids-2026-08-09.md` v2
> **감사 기준**: R1 지적사항이 v2에 실제 반영됐는지, 현재 `backend/app/` 코드와
> 맞는지, 구현 착수 전 막아야 할 신규 결함이 있는지 독립 검증.

## 판정 요약

| # | R1 지적 / 검증 항목 | R2 판정 | 구현 착수 영향 |
|---|---|---|---|
| 1 | Shopify `product.id` 대신 `variant.id` 저장 | **해결됨** | 방향 맞음. 단, 예시 JSON/선행조사 문구 일부는 product id 중심이라 정리 필요 |
| 2 | `matcher.py` 통합을 Phase 2로 앞당김 | **부분해결** | 순서는 고쳤지만 실제 `get_or_create_product` 시그니처/호출 경로 변경 범위가 불충분 |
| 3 | `_merge_products` 병합 시 고아 매핑 이전 | **부분해결** | 자동/수동 병합 모두 공유 함수 경유 확인. 단, v2 예시의 import/공유 helper/테스트 명세가 부족 |
| 4 | Rakuten `itemCode` 셀러 종속성 | **해결됨** | 신규 확정 fast-path 제외 방침이 맞음 |
| 5 | Celery 동시성 `ON CONFLICT` upsert | **부분해결** | upsert 예시는 있으나 conflict 시 `product_id` 충돌 정책이 명시되지 않음 |
| 6 | Amazon ASIN 추출 정규식 의존 | **해결됨** | PA-API `ASIN`, HTML `data-asin` 우선 방침이 코드와 맞음 |
| 7 | `platform_name` 대신 `platform_id` FK 및 역방향 인덱스 | **해결됨** | 기존 `Platform`/`SaleEvent` 타입·명명과 정합 |
| 8 | 자체발견 1: `catalog.py` 시딩 충돌 | **부분해결** | 언급은 됐지만 실제 시딩은 `Product`만 만들며 `Platform` 조회 경로가 필요 |
| 9 | 자체발견 2: 관리자 수동 승인 병합 | **해결됨** | 실제 `admin.py`는 `_merge_products`를 재사용하므로 공유 함수 수정으로 같이 해결됨 |
| 10 | 자체발견 3: Rakuten 리스팅 무제한 적재 | **부분해결** | `last_seen_at`은 추가됐지만 TTL/아카이빙은 범위 밖이라 테이블 오염은 후속 리스크로 남음 |

## 상세

### 1. Shopify 식별자 레벨 — 해결됨

R1의 핵심 지적은 맞았고 v2는 올바르게 수정했다. 실제
`backend/app/scrapers/brands/shopify.py`는 `product.get("variants")`를 순회하며
variant별 가격·용량으로 `ScrapedEvent`를 만든다. 같은 `product.id`를 여러 용량에
저장하면 `(platform_id, external_id)` 유니크 충돌이 난다. v2의
`external_id = variant.id`, `id_type = "variant_id"`, `handle` 미저장 결정은 코드 구조와
맞다.

남은 정리점: v2 1절 예시와 선행조사 표에는 아직 최상위 `id`/`handle`을 "고유
번호/별칭"으로 채택한다는 표현이 남아 있다. 3-1절 결론과 충돌하므로 구현자 혼선을
막기 위해 예시 JSON에 `variants: [{id: ...}]`를 추가하고 선행조사 표의 채택 판단을
`variant.id` 기준으로 고쳐야 한다.

### 2. matcher.py Phase 2 통합 — 부분해결

R1이 지적한 크래시 시나리오는 실제다. 현재 `backend/app/ai/matcher.py`의
`get_or_create_product(db, name, brand, country)`는 external id를 받을 방법이 없고,
먼저 이름 기반 `find_matching_product`를 호출한 뒤 실패하면 새 `Product`를 만든다.
`backend/app/scrapers/collector.py`도 `get_or_create_product(db, product_name, brand,
platform_country)`만 호출한다. 따라서 v2가 "Phase 2에서 matcher 최우선 fast-path를
동시 배포"로 앞당긴 것은 맞다.

다만 v2의 5-3절 예시는 `find_by_external_id` helper만 보여주고,
`get_or_create_product`의 새 계약을 닫지 않는다. 구현 설계에는 최소한 다음이
명시돼야 한다.

- `ScrapedEvent`에 `external_id: str | None`, `id_type: str | None` 필드 추가.
- `collector.py`가 같은 `product_name` 그룹 안에서 external id를 어떻게 고를지 명시.
  Shopify는 같은 상품명에 여러 variant가 들어오므로 event별 external id를 모두 저장해야 한다.
- `get_or_create_product` 시그니처를 `platform_id`, `external_id`, `id_type` 선택 인자로
  확장하거나, collector 레벨에서 fast-path 조회 후 matcher를 호출하는지 하나로 확정.
- 새 `Product` 생성과 `platform_product_ids` upsert를 같은 트랜잭션에서 수행하는 위치.

현재 v2 상태로는 "순서"는 고쳤지만 실제 크래시 방지 구현 경계가 충분히 명세되지 않았다.

### 3. 병합 시 고아 매핑 — 부분해결

실제 `backend/app/tasks/match_products.py`의 `_merge_products`는 `orphan.deleted_at`을
찍고 `SaleEvent.product_id`만 canonical로 옮긴다. R1의 고아 매핑 지적은 타당하다.
v2 5-1절의 방향도 맞다. `tuple_(platform_id, external_id).in_(select(...))` 형태는
PostgreSQL row-value 비교로 컴파일된다.

중요한 확인: `backend/app/api/admin.py`의 수동 승인 경로는 별도 병합 로직이 아니라
`from app.tasks.match_products import _merge_products` 후 승인 API에서 그대로 호출한다.
따라서 v2 5-2절의 "별개 경로로 병합을 수행한다면"은 실제보다 약하다. 정확한 결론은
"`_merge_products`를 공유 helper로 유지하고 그 함수에 매핑 이전을 넣으면 자동/수동
승인이 같이 해결된다"다.

남은 정리점: 예시 코드에 필요한 `delete`, `update`, `select`, `tuple_`, `PlatformProductId`
import가 명시돼야 한다. 또한 이 병합 로직은 `match_products.py` 안에 직접 둘지,
`app/ai/platform_product_ids.py` 같은 helper로 뺄지 확정해야 한다.

### 4. 신규 컬럼 타입·명명 — 해결됨

`platform_id` FK는 현행 `SaleEvent.platform_id`와 같은
`UUID(as_uuid=True), ForeignKey("platforms.id")` 패턴과 맞다. `Platform.id`도 UUID다.
`created_at`/`last_seen_at`의 `DateTime(timezone=True), server_default=func.now()` 역시
기존 `Product`, `SaleEvent`, `ProductMatchCandidate` 관례와 맞다.

`id_type`은 문자열 enum 후보가 아직 DB enum이 아니라 `String(50)`으로 제안돼 있는데,
현 프로젝트는 일부 고정값에 SQLAlchemy `Enum`도 쓰고 있다. 그래도 이 값은 플랫폼별로
확장될 가능성이 있어 `String(50)` + 테스트 assert가 더 단순하고 적합하다.

### 5. v2 신규 결함

#### [P1] 대상 파일 목록이 실제 변경 경계를 빠뜨린다

v2 상단 대상 파일에는 `backend/app/scrapers/base.py`와 `backend/app/scrapers/collector.py`가
없다. 하지만 현재 `ScrapedEvent` dataclass에는 external id 필드가 없고, collector는
matcher 호출과 event persist를 분리한다. 이 둘을 건드리지 않으면 Shopify가
`variant.id`를 싣고 와도 저장 경로가 없다.

#### [P1] upsert 충돌 정책이 `product_id` 불일치를 덮을 수 있다

v2 5-3절은 conflict 시 `last_seen_at`만 갱신한다. 기존 행이 `(platform_id, external_id) ->
P1`인데 새 코드가 같은 식별자를 P2에 붙이려는 상황이면, 이건 단순 관측 갱신이 아니라
정합성 충돌이다. `product_id`를 조용히 유지하면 새 `Product` P2가 생긴 채 매핑만 P1에
남을 수 있고, `product_id`까지 update하면 오히려 잘못된 재귀속이 된다.

권장: fast-path 조회를 upsert보다 먼저 강제하고, upsert conflict에서 기존
`product_id != product_id`가 감지되면 `PlatformProductIdConflict` 같은 명시적 에러를
내거나 기존 product를 반환하도록 계약을 분리한다. 조용한 `last_seen_at` 갱신만으로는
R1의 "신규 Product 생성 후 unique 충돌" 계열을 완전히 닫지 못한다.

#### [P2] `onupdate=func.now()`는 bulk upsert의 자동 갱신 보장이 아니다

모델 컬럼의 `onupdate`는 ORM update 경로에서 의미가 있고, v2의 `pg_insert...
on_conflict_do_update`에서는 `set_={"last_seen_at": func.now()}`를 직접 넣어야 한다.
v2 예시는 직접 넣고 있어 동작은 맞지만, 컬럼 설명의 "(자동, `onupdate=func.now()`)"만
읽으면 구현자가 upsert set을 생략할 수 있다. 컬럼 설명을 "server_default + upsert set에서
직접 갱신"으로 바꾸는 편이 안전하다.

#### [P2] Phase 3의 Rakuten 저장 정책이 아직 모호하다

v2는 Rakuten `itemCode`를 fast-path에서 제외한다고 했지만, "기록용"으로 어느 범위까지
저장할지 확정하지 않았다. 현재 Rakuten API는 `hits=10`, 가격순이라 한 검색어마다 여러
셀러 리스팅이 계속 바뀔 수 있다. `last_seen_at`만으로는 행 증가를 막지 못한다.
Phase 3에 들어가기 전 "공식몰만 저장", "상위 N개만 저장", "JAN 없으면 저장 보류" 중
하나를 정해야 한다.

## Act-Based Verification

순수 설계 감사라 서비스 실행은 하지 않았다. 대신 실제 코드 경로를 읽고,
v2 5-1절의 SQLAlchemy `tuple_(...).in_(select(...))` 예시가 PostgreSQL dialect로
`DELETE ... WHERE (platform_id, external_id) IN (SELECT ...)` 형태로 컴파일됨을
로컬 venv에서 확인했다.

## 최종 결론

**NEEDS_REVISION**

R1의 큰 방향은 v2에 대부분 반영됐다. 특히 Shopify `variant.id`, `platform_id` FK,
Amazon ASIN 추출, Rakuten fast-path 제외, matcher Phase 2 선행은 맞다.

하지만 이 설계 그대로 구현 착수하기에는 Phase 2의 실제 코드 계약이 덜 닫혔다.
구현 전 v2에 아래 5가지를 반영해야 한다.

1. 상단 대상 파일에 `backend/app/scrapers/base.py`, `backend/app/scrapers/collector.py` 추가.
2. `ScrapedEvent` 외부 식별자 필드와 collector 저장 흐름을 명시.
3. `get_or_create_product` 새 시그니처 또는 collector fast-path 위치를 확정.
4. upsert conflict 시 기존 `product_id`와 신규 `product_id`가 다를 때의 명시적 처리 정책 추가.
5. Shopify 예시/선행조사 표의 `product.id`/`handle` 채택 표현을 `variant.id` 기준으로 정정.

이 5개를 고치면 구현 착수 가능 상태로 볼 수 있다.
