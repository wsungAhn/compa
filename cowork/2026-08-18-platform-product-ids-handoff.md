# Codex Handoff — 2026-08-18 · platform_product_ids (외부 상품 식별자 저장)

> **상태(Status):** `대기 / pending`
> _(Executor: 시작 시 `진행중 / in-progress`, 완료 시 `검토대기 / review-pending`.
>  `완료 / done`은 리뷰어만 커밋 후 설정.)_
>
> **작성자(Author):** Claude Sonnet 5 (설계 v2~v5, 랩탑 D:\dev\compa) → **수행자(Executor):** Codex CLI
> **작업명(Task):** `platform_product_ids` 테이블 신설 + Shopify 공홈 fast-path 통합 (설계 2단계까지)
> **설계 근거(Design basis):** `docs/design-platform-product-ids-2026-08-09.md` (v5) —
> **반드시 먼저 전체를 읽을 것.** 4라운드 적대적 감사(R1 Gemini → Codex R2 → Codex R3 →
> Gemini R4)를 거쳐 수렴한 문서다. §4(구현 순서)·§5(병합·동시성)·§7(완료 판정)이 이
> 핸드오프의 정본이며, 아래 내용과 어긋나면 설계문서가 우선한다. 감사 히스토리:
> `docs/audit-platform-product-ids-2026-08-18-gemini-r1.md`,
> `docs/audit-platform-product-ids-2026-08-18-codex-r2.md`,
> `docs/audit-platform-product-ids-2026-08-18-codex-r3.md`,
> `docs/audit-platform-product-ids-2026-08-18-gemini-r4.md` — 참고용, 굳이 안 읽어도
> v5 설계문서에 전부 반영돼 있음.
> **범위(Scope):** in — 설계 §4의 **1단계+2단계만**(Alembic 마이그레이션, 신규 모델,
> `ScrapedEvent` 필드, `collector.py`의 fast-path/upsert/헬퍼 3종, `tasks/collect.py`의
> `_collect_all` fast-path, `brands/shopify.py` variant 식별자 채워넣기, §5-1/5-2의
> `_merge_products` 매핑 이전). out — 설계 §4 **3단계**(Rakuten/Amazon 스크래퍼에
> `item_code`/`asin` 채워넣기 — 후속 핸드오프로 분리), §8의 P2 2건(`collected_product_ids`
> 반환 정합성, `_match_pending_products` 스캔 범위 확장 — 후속 이슈), `catalog.py` 시딩
> 통합(§4 6번 — 2단계 완료 후 별도 확인).

---

## 0. How to use this document (Executor, read first)

너에게는 이 프로젝트의 맥락도 이전 대화도 없다. 아래 내용과 설계문서(v5)만 신뢰하라.

- **하지 마라:** 범위 밖 리팩터(Rakuten/Amazon 스크래퍼 수정 포함) · 라이브/프로덕션
  진입점 실행 · 프로덕션 설정 변경 · **커밋**(워킹트리만 남기고 리뷰어에게 넘긴다) ·
  main 머지 · worker/beat/api 재시작 · `.env` 생성·수정
- **항상:** 각 Task 후 테스트 실행 → 통과 확인 → 다음 Task. 작업 내용을 §8(아래)에 기록.
  시작·완료 시 맨 위 상태줄 변경
- **확신 없으면:** 추측하지 마라. 설계문서 v5의 해당 절을 다시 읽고, 그래도 애매하면
  멈추고 §8에 질문을 남겨라 — 특히 5-3절의 `upsert_platform_product_id` 소프트삭제
  분기는 이 설계에서 가장 많이 틀렸던 부분(R2→R3→R4 세 라운드에 걸쳐 수정됨)이니
  코드 예시를 그대로 옮기고 임의로 단순화하지 마라.

### Execution environment

- **cwd: `backend/`** (레포 루트가 아니다. 파일 경로는 전부 `backend/` 기준)
- Interpreter: `/Users/Mung/dev/compa/backend/.venv/bin/python` (Python 3.11.8)
- Tests: `PYTHONPATH=. /Users/Mung/dev/compa/backend/.venv/bin/python -m pytest tests/ -q`
- Type check: `PYTHONPATH=. /Users/Mung/dev/compa/backend/.venv/bin/python -m mypy --strict app/`
- Frontend는 이 작업 범위 밖(백엔드만 건드림) — `npm run build`/`lint` 불필요.
- **현재 테스트 베이스라인 (2026-08-18 실측): `502 passed, 1 skipped` (15.02s).**
  이 아래로 떨어지면 회귀다. 그 1 skipped는 원래 그렇다
  (`tests/scrapers/test_amoremall.py:160`, "실제 Playwright/네트워크 호출 — CI에서
  스킵"). **건드리지 마라.**
- **T1(마이그레이션)·병합/upsert 테스트는 살아있는 로컬 PostgreSQL이 필요할 수 있다**
  (`postgresql+asyncpg://compa:compa@localhost:5432/compa`). DB에 못 닿으면 그 테스트만
  skip으로 나올 수 있다 — **그건 예상된 상황이니 테스트를 "고치지" 마라.** 특히 넓은
  `try/except`로 감싸서 실패를 숨기지 마라. §8에 "내 환경에서 어떤 테스트가 passed였는지
  skipped였는지"를 정확히 적어라 — 스킵을 통과로 보고하지 마라. 리뷰어가 DB 있는 환경에서
  직접 재실행해 최종 판정한다.
- 상시 데몬: compa는 launchd로 worker/beat/api 3개가 상시 가동 중이다
  (`com.compa.worker` / `.beat` / `.api`). **재시작하지 마라** — 이 작업은 새 코드를
  운영에 반영하는 게 아니라 워킹트리에 구현만 남기는 것.

---

## 1. Background (why this work)

compa는 화장품 가격 추적 서비스다. 지금은 "이 한국 상품과 저 일본 상품이 같은
물건인가?"를 이름 문자열 비교(+ 애매하면 Claude LLM 호출)로 판단한다. 각 소스
플랫폼(Rakuten/Amazon/Shopify 공홈)이 이미 안정적인 고유 식별자를 API 응답에
주고 있는데도 compa는 그걸 읽고 버린다 — 그래서 이름이 조금만 바뀌어도(리브랜딩,
시즌 문구, 오타) 매칭이 흔들리고, 이게 과거 LLM 크레딧 전소 사고의 원인 중 하나였다.

이 작업은 `platform_product_ids`라는 작은 매핑 테이블 하나를 도입해서, "이름 추측"
대신 "번호 대조"로 상품을 연결하는 fast-path를 만드는 것. 자세한 배경과 구체적
예시는 설계문서 v5의 §0~§1을 읽어라.

---

## 2. Task 목록 (설계 §4의 1·2단계, §5-1/5-2)

### T1 — Alembic 마이그레이션 + 모델

- `backend/app/models/platform_product_id.py` 신규 — 설계 §3의 스키마 그대로:
  `id`(UUID PK), `product_id`(FK→products.id, `ON DELETE CASCADE`),
  `platform_id`(FK→platforms.id), `external_id`(String), `id_type`(String(50)),
  `created_at`, `last_seen_at`. 유니크 제약 `(platform_id, external_id)`,
  `product_id` 단독 인덱스 추가.
- `backend/app/models/__init__.py`에 등록.
- `alembic revision --autogenerate -m "add platform_product_ids"` — 현재 마이그레이션
  체인 head 확인 후 그 뒤에 연결(`backend/alembic/versions/` 최신 파일 확인).
- 검증: `alembic upgrade head`가 로컬 PG에서 에러 없이 통과.

### T2 — `ScrapedEvent` 필드 추가

- `backend/app/scrapers/base.py`의 `ScrapedEvent` dataclass에
  `external_id: str | None = None`, `id_type: str | None = None` 추가.

### T3 — `collector.py`에 helper 3종 추가

설계 §5-3의 코드를 **그대로** 옮긴다(요약하지 말 것 — 소프트삭제 분기가 핵심이다):

- `find_by_external_id(db, platform_id, external_id) -> Product | None`
- `upsert_platform_product_id(db, product_id, platform_id, external_id, id_type) -> uuid.UUID`
  — 기존 매핑이 없으면 insert, 있고 살아있으면 `last_seen_at`만 갱신(기존
  product_id 유지), **있는데 그 product가 소프트 삭제됐으면 새 product_id로
  재할당**. 이 세 갈래를 빠뜨리지 말 것.
- `resolve_product_by_external_id(db, platform_id, events) -> Product | None`
  — 이벤트 그룹을 순회하며 `id_type == "item_code"`(Rakuten)는 건너뛰고
  `find_by_external_id` 시도.

### T4 — `_collect_platform` fast-path 배선 (설계 §4-3, §4-4)

- `get_or_create_product` 호출 직전(현재 `collector.py:309` 부근)에
  `resolve_product_by_external_id` 먼저 호출 → 찾으면 그 Product 사용,
  `get_or_create_product` 스킵. 못 찾으면 기존대로 폴백.
- `persist_events_for_product` 내부 루프 순서 변경: 이벤트별로
  `s.external_id`가 있으면 **`upsert_platform_product_id`를 `SaleEvent` insert보다
  먼저** 호출하고, 반환된 product_id를 그 `SaleEvent.product_id`로 사용(인자로
  받은 `product.id`를 그대로 믿지 말 것). 반환값이 인자와 다르면
  `logger.warning`.

### T5 — `tasks/collect.py:_collect_all` fast-path 배선 (설계 §4-5)

- `find_exact_for_sweep` 호출 **전에** `resolve_product_by_external_id`(T3에서
  만든 것, `collector.py`에서 import)를 먼저 시도. 찾으면 그 Product로 확정하고
  `find_exact_for_sweep` 스킵. 둘 다 실패하면 기존과 동일하게 `skipped_groups += 1`.

### T6 — `brands/shopify.py`에 variant 식별자 채워넣기

- `parse_products`의 variant 루프 안에서 `ScrapedEvent(..., external_id=str(variant.get("id")), id_type="variant_id")`.
  `handle`은 쓰지 않는다(설계 §3-1 근거).

### T7 — `_merge_products` 매핑 이전 (설계 §5-1)

- `backend/app/tasks/match_products.py`의 `_merge_products`에 설계 §5-1 코드
  그대로 추가: canonical에 이미 있는 `(platform_id, external_id)`는 orphan 쪽
  삭제, 나머지는 orphan→canonical로 소유권 이전.
- `backend/app/api/admin.py`는 `_merge_products`를 그대로 호출하는 구조라
  별도 수정 불필요(설계 §5-2 — 실제로 그런지 코드로 재확인만 하고 넘어갈 것).

---

## 3. 완료 판정 — 설계 §7 전체를 테스트로 구현

설계문서 §7에 나열된 9개 항목을 전부 단위/통합 테스트로 작성하고 통과시켜라.
**특히 아래 2개는 반드시 포함(과거 라운드에서 가장 많이 놓쳤던 지점):**

- **소프트 삭제 재할당 테스트**: 매핑이 가리키는 product를 삭제(`deleted_at` 설정)한
  뒤 같은 external_id로 다시 upsert → 새 product_id로 재할당되는지, 이 시나리오를
  두 번 반복해도 고아 Product가 매번 늘지 않는지(무한루프 회귀 방지).
- **`_collect_all` fast-path 테스트**: 상품명이 바뀌어 `find_exact_for_sweep`가
  실패하는 상황을 시뮬레이션해도 external_id로 기존 Product를 찾아 갱신하는지.

`mypy --strict` 0 errors, 기존 502 passed 유지 + 신규 테스트 전부 통과가 완료 조건.

---

## 4. Executor Log (여기에 기록)

_시작 시 위 상태줄을 `진행중 / in-progress`로, 완료 시 `검토대기 / review-pending`으로
바꾸고, 아래에 Task별 진행 상황·발견한 문제·테스트 결과(pass/skip 구분)를 남겨라._
