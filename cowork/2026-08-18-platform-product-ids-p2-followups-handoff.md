# Codex Handoff — 2026-08-18 · platform_product_ids P2 후속 2건

> **상태(Status):** `대기 / pending`
>
> **작성자(Author):** Claude Sonnet 5 (랩탑 D:\dev\compa) → **수행자(Executor):** Codex CLI
> **작업명(Task):** 설계 §8(P2 2건) 반영 — (1) `collected_product_ids` 반환 정합성
> [검색 정확도 직결, 우선순위 높음], (2) 빈 고아 Product 주기적 정리 [DB 위생, 검색
> 정확도엔 영향 없음]
> **설계 근거(Design basis):** `docs/design-platform-product-ids-2026-08-09.md` (v5)
> §8. 1·2·3단계 구현은 커밋 `beef41d`, `3e25c99`로 이미 완료·검증됨.
> **범위(Scope):** in — `backend/app/scrapers/collector.py`
> (`persist_events_for_product`/`_collect_platform`/`collect_fast`/`collect_on_demand`),
> 신규 정리 배치(파일 위치는 아래 T2 참고) + 각각 테스트. out — 다른 리팩터, 스키마
> 변경(T2는 기존 컬럼만 사용).

---

## 0. How to use this document (Executor, read first)

- **하지 마라:** 범위 밖 수정 · 커밋 · main 머지 · worker/beat/api 재시작 ·
  `.env` 생성·수정
- **항상:** 각 Task 후 테스트 실행 → 통과 확인. §4에 기록. 시작·완료 시 상태줄 변경.
- **확신 없으면:** 멈추고 §4에 질문 남겨라.

### Execution environment

- cwd: `backend/` · Interpreter: `/Users/Mung/dev/compa/backend/.venv/bin/python`
- Tests: `PYTHONPATH=. /Users/Mung/dev/compa/backend/.venv/bin/python -m pytest tests/ -q`
- Type check: `PYTHONPATH=. /Users/Mung/dev/compa/backend/.venv/bin/python -m mypy --strict app/`
- **현재 베이스라인(2026-08-18, 3단계까지 구현 후 실측): `515 passed, 1 skipped`.**
- DB 의존 테스트는 sandbox에서 skip/blocked가 나올 수 있다 — 정직하게 기록,
  리뷰어가 재검증한다.

---

## 1. 배경 — 왜 이게 검색 정확도 문제인가

사용자가 검색하면 `collect_fast`/`collect_on_demand`(둘 다 이 파일 안)가
`_collect_platform`을 플랫폼별로 병렬 실행하고, 각 호출이 반환하는
`collected_product_ids`를 `set().union(...)`으로 합친 뒤 `_products_with_events`로
"방금 수집돼서 이벤트가 붙은 상품만" 걸러 사용자에게 돌려준다.

그런데 `_collect_platform`은 `collected_product_ids.add(prod.id)`를 **fast-path/이름
매칭으로 고른 product의 id**로 채운다(현재 426행). 실제로 이벤트가 어느 product에
붙었는지는 그 안에서 호출하는 `persist_events_for_product`가 결정하는데(5-3절 —
같은 external_id가 이미 다른 product를 가리키면 그 다른 product로 재귀속된다),
`persist_events_for_product`는 지금 삽입 건수(`int`)만 반환하고 실제 사용된
product_id는 호출자에게 알려주지 않는다.

**결과**: 재귀속이 발생한 검색에서는, 사용자가 방금 검색을 트리거해서 실제로 DB에
새 가격 정보가 저장됐는데도 `_products_with_events`가 그 상품을 몰라서 **검색
응답에서 누락될 수 있다.** 흔한 케이스는 아니지만(재귀속 자체가 드묾), 발생하면
"방금 분명히 갱신됐는데 검색 결과엔 안 뜬다"는 사용자 체감 버그가 된다.

---

## 2. Task 목록

### T1 — `collected_product_ids` 반환 정합성 (검색 정확도, 우선순위 높음)

1. `persist_events_for_product`의 반환 타입을 `int`(삽입 건수)에서
   `tuple[int, set[uuid.UUID]]`(삽입 건수, 실제 사용된 authoritative product_id
   집합)로 바꾼다. 루프 안에서 `authoritative_product_id`를 이미 계산하고 있으니
   (304-320행), 매 이벤트마다 그 값을 집합에 추가하면 된다. confidence=0으로
   skip된 이벤트는 집합에 안 넣는다(애초에 안 쓰였으니까).
2. 호출부 3곳 전부 시그니처 변경에 맞춰 수정:
   - `_collect_platform`(374행 부근): `await persist_events_for_product(...)`의
     반환값에서 `(_, used_product_ids) = ...`를 받아
     `collected_product_ids.update(used_product_ids)`로 바꾼다(`prod.id`만
     add하던 걸 대체). `used_product_ids`가 비어있으면(이벤트가 전부 skip됐거나
     external_id가 없었던 경우) 기존처럼 `prod.id`를 fallback으로 넣는다 —
     "아무것도 재귀속 안 됐으면 원래 product가 맞다"는 뜻이니까.
   - `tasks/collect.py:_collect_all`(브랜드 카탈로그 스윕)도
     `persist_events_for_product`를 직접 호출하니(현재 `inserted_here = await
     persist_events_for_product(...)`) 튜플 언패킹으로 맞춰준다. 이 함수는
     `collected_product_ids` 개념이 없으니(반환값을 카운트에만 씀) 카운트
     집계 로직만 튜플의 첫 원소를 쓰도록 고치면 된다.
3. `collect_fast`/`collect_on_demand`는 `_collect_platform`의 반환값을 그대로
   쓰는 쪽이라 별도 수정 불필요할 것 — 확인만 해라.

### T2 — 빈 고아 Product 주기적 정리 (DB 위생, 검색에 영향 없음 — 낮은 우선순위)

**`_match_pending_products`의 스캔 범위를 넓히지 마라** — 그 함수는 "일본/한국 등
비영문 플랫폼에서 온, name_en 없는 상품에 이름 매칭을 시도"하는 별개 목적이다.
빈 고아(이벤트 0개) 정리는 그것과 다른 문제다.

1. `backend/app/tasks/`에 새 Celery task 추가(파일명은 기존 컨벤션 참고 —
   예: `cleanup.py` 또는 기존 `match_products.py`에 별도 함수로 추가해도 됨,
   기존 task 구조를 보고 자연스러운 쪽으로 판단해라):
   `SaleEvent`가 하나도 없고, `created_at`이 **24시간 이상 지난** `Product`를
   소프트 삭제(`deleted_at`)한다. 24시간 유예를 두는 이유: 방금 생성된 고아가
   아직 다른 플랫폼 수집이 안 끝나서 이벤트가 안 붙었을 수도 있으니, 너무
   빨리 지우면 안 된다.
   - 쿼리: `Product.deleted_at.is_(None)` AND 해당 product를 참조하는
     `SaleEvent`가 (deleted 여부 상관없이 — 과거에 이벤트가 있었다가 다
     삭제된 것과 "애초에 한 번도 없었던" 것은 구분) 존재하지 않음 AND
     `created_at < now() - 24h`.
   - `platform_product_ids`도 같이 정리할지는 FK가 `ON DELETE CASCADE`인지
     확인해서(설계 §3 — CASCADE로 설계됨) product 삭제만으로 매핑도 정리되는지
     확인해라. 소프트 삭제(`deleted_at`만 세팅)라 CASCADE는 안 타니, 이
     task에서 매핑도 같이 정리할지 판단해서 남겨라(정리 안 해도 fast-path
     조회가 `deleted_at IS NULL`을 걸러서 기능상 문제는 없다 — 다만 DB
     행 누적은 계속됨. 시간 되면 같이 정리, 아니면 이 판단을 §4에 남기고
     넘어가도 됨).
2. Celery beat 스케줄 등록은 **하지 마라** — 이번 작업은 task 함수 자체만
   만들고, 언제 얼마나 자주 돌릴지는 범위 밖(사람이 결정).
3. 테스트: 이벤트 없는 24시간 지난 Product는 정리되는지, 24시간 안 지났으면
   안 지워지는지, 이벤트 있는 Product는 안 지워지는지.

---

## 3. 완료 판정

- `mypy --strict` 0 errors 유지
- 베이스라인(515 passed, 1 skipped) 유지 + 신규 테스트 전부 통과
- T1: 재귀속 시나리오 통합 테스트 — external_id가 다른 product로 재귀속되는
  상황을 만들어서 `_collect_platform`(또는 `collect_on_demand`)의 반환 집합에
  **재귀속된 product_id가 포함되는지**(원래 product_id가 아니라) 확인. 이게
  이 작업의 핵심 회귀 테스트.
- T2: 위 3가지 케이스(24h 지난 빈 고아 정리됨/24h 안 지남/이벤트 있음)

---

## 4. Executor Log (여기에 기록)
