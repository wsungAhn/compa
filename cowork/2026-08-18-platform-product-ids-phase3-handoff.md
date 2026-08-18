# Codex Handoff — 2026-08-18 · platform_product_ids Phase 3 (Rakuten/Amazon 식별자)

> **상태(Status):** `대기 / pending`
> _(Executor: 시작 시 `진행중 / in-progress`, 완료 시 `검토대기 / review-pending`.
>  `완료 / done`은 리뷰어만 커밋 후 설정.)_
>
> **작성자(Author):** Claude Sonnet 5 (랩탑 D:\dev\compa) → **수행자(Executor):** Codex CLI
> **작업명(Task):** Rakuten/Amazon 스크래퍼가 `ScrapedEvent.external_id`/`id_type`를
> 채워 넣도록 확장 (설계 §4 3단계, 1·2단계는 커밋 `beef41d`로 이미 구현·검증 완료)
> **설계 근거(Design basis):** `docs/design-platform-product-ids-2026-08-09.md` (v5)
> §3-2(Rakuten)·§3-3(Amazon)·§4 3단계. fast-path/upsert 인프라(1·2단계)는 이미
> `backend/app/scrapers/collector.py`에 구현돼 있다 — 이 작업은 **스크래퍼 2개가
> 그 인프라에 값을 채워 넣기만 하면 된다.** collector.py/tasks/collect.py는
> 건드릴 필요 없음(이미 `resolve_product_by_external_id`가 `id_type == "item_code"`를
> 자동으로 fast-path에서 제외하도록 돼 있음 — Rakuten용 특별 처리 불필요).
> **범위(Scope):** in — `backend/app/scrapers/jp/rakuten.py`(itemCode 채워넣기),
> `backend/app/scrapers/us/amazon.py`(PA-API `ASIN` 필드 + HTML `data-asin` 속성
> 채워넣기), 각각 대응 테스트. out — collector.py/tasks/collect.py 수정(불필요),
> 다른 스크래퍼(Sephora/Ulta/Tmall 등 — 이번 설계 범위 밖), JAN 코드 조사(§4 4단계,
> 별도 후속).

---

## 0. How to use this document (Executor, read first)

- **하지 마라:** 범위 밖 파일 수정 · 커밋 · main 머지 · worker/beat/api 재시작 ·
  `.env` 생성·수정
- **항상:** 각 Task 후 테스트 실행 → 통과 확인. 작업 내용을 §3(아래)에 기록.
  시작·완료 시 맨 위 상태줄 변경
- **확신 없으면:** 멈추고 §3에 질문 남겨라.

### Execution environment

- cwd: `backend/` · Interpreter: `/Users/Mung/dev/compa/backend/.venv/bin/python`
- Tests: `PYTHONPATH=. /Users/Mung/dev/compa/backend/.venv/bin/python -m pytest tests/ -q`
- Type check: `PYTHONPATH=. /Users/Mung/dev/compa/backend/.venv/bin/python -m mypy --strict app/`
- **현재 베이스라인(2026-08-18, 1·2단계 구현 후 실측): `511 passed, 1 skipped`.**
  이 아래로 떨어지면 회귀다.
- DB 의존 테스트는 이전 핸드오프와 동일하게 sandbox에서 skip/blocked가 나올 수
  있다 — 정직하게 기록하고 리뷰어가 재검증한다. 이번 작업은 순수 파싱 로직이라
  DB 없이도 대부분 검증 가능할 것.

---

## 1. Task 목록

### T1 — Rakuten `itemCode` 채워넣기

- `backend/app/scrapers/jp/rakuten.py`의 `parse_response`(현재 18-48행 부근)에서
  `item.get("itemCode")`를 읽어 `ScrapedEvent(..., external_id=item.get("itemCode"), id_type="item_code")`로
  채운다. `itemCode`가 없으면 `external_id=None`으로 둔다(기존 로직 그대로 나머지
  필드 유지).
- **주의**: 설계 §3-2에 따라 이 값은 fast-path의 "신규 상품 확정" 판단에는 안 쓰인다
  (`resolve_product_by_external_id`가 `id_type == "item_code"`를 이미 건너뛰게
  구현돼 있음 — collector.py 수정 불필요, 값만 정확히 채워 넣으면 인프라가 알아서
  처리한다). `platform_product_ids`에는 기록되지만 "이 셀러가 이 상품을 판다"는
  용도로만 쓰인다는 걸 테스트 docstring에 남겨라.
- 테스트: `tests/scrapers/test_rakuten.py`에 `itemCode`가 있는/없는 응답 각각에서
  `external_id`/`id_type`가 정확히 채워지는지 확인.

### T2 — Amazon ASIN 채워넣기 (PA-API + HTML 폴백 둘 다)

- `backend/app/scrapers/us/amazon.py`의 `parse_paapi_response`(142-220행)에서
  `item.get("ASIN")`을 읽어 `ScrapedEvent(..., external_id=item.get("ASIN"), id_type="asin")`.
  PA-API 응답 item에는 최상위에 `ASIN` 필드가 있다(정규식으로 URL 파싱 불필요 —
  설계 §3-3이 v1의 정규식 방식을 이미 폐기한 이유).
- `parse_search_html`(231-316행)에서 각 결과 컨테이너
  (`div[data-component-type="s-search-result"]`, 루프 변수 `item`)는 그 자체가
  `data-asin` 속성을 갖고 있다 — `item.get("data-asin")`으로 직접 읽어
  `external_id`/`id_type="asin"`에 채운다. 이 속성이 없으면(스폰서/변형 마크업 등)
  `external_id=None`으로 둔다 — **정규식 폴백을 추가하지 마라**, 설계가 명시적으로
  "실패를 조용히 삼키고 확인 안 된 값을 저장하지 않는다"고 정했다.
- 테스트: `tests/scrapers/test_amazon.py`(또는 해당 파일명)에 PA-API 응답과 HTML
  양쪽 경로에서 ASIN 있음/없음 케이스 각각 확인.

---

## 2. 완료 판정

- `mypy --strict` 0 errors 유지
- 베이스라인(511 passed, 1 skipped) 유지 + 신규 테스트 전부 통과
- Rakuten/Amazon 각각 최소 1개 이상 실제스러운 fixture로 `external_id`/`id_type`가
  올바르게 채워지는 통합 성격 테스트 존재
- **회귀 확인**: 기존 Shopify fast-path/merge 테스트(1·2단계 구현분)가 이 변경으로
  영향받지 않는지 — 영향 없을 것으로 예상되나 전체 스위트 실행으로 확인

---

## 3. Executor Log (여기에 기록)
