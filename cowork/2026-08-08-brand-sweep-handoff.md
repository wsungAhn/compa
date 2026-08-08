# Codex Handoff — 2026-08-08 · 브랜드 공홈 카탈로그 스윕 (B)

> **상태(Status):** `대기중 / pending`
> _(Executor: 시작 시 `진행중 / in-progress`, 완료 시 `검토대기 / review-pending`.
>  `완료 / done`은 리뷰어만 커밋 후 설정.)_
>
> **시작 기록(Started by):** `session=2c299c4f-c3a2-492e-83a9-a24fd2b61acf machine=mac-studio started=2026-08-08T09:47:07-0700`
>
> **작성자(Author):** Claude Opus 5 (설계·리뷰) → **수행자(Executor):** Codex CLI
> **작업명(Task):** 일일 수집을 상품별 검색에서 브랜드 카탈로그 스윕으로 전환
> **설계 근거(Design basis):** `docs/design-daily-collect-brand-sweep-2026-08-07.md`
> — **반드시 전문을 먼저 읽어라. 이 핸드오프보다 설계문서가 우선한다.**
> 적대적 감사 **6라운드**(지적 33건 전건 반영, 기각 0)를 거친 문서다. 라운드 기록은
> `docs/audit-b-r1.md` ~ `audit-b-r6.md`.

---

## 0. How to use this document (Executor, read first)

너에게는 이 프로젝트의 맥락도 이전 대화도 없다. 아래와 설계문서만 신뢰하라.

- **하지 마라:** 범위 밖 리팩터 · **커밋** · main 머지 · worker/beat/api 재시작 ·
  `.env` 수정(`.env.example`은 예외, §4.2.-1이 지시) · 라이브 수집 실행(스모크는 리뷰어가)
- **항상:** 각 Task 후 테스트 → 통과 확인 → 다음. §8에 기록. 상태줄 갱신
- **확신 없으면:** 추측하지 마라. 멈추고 §8에 질문을 남겨라

### Execution environment

- **cwd: `backend/`** (파일 경로는 전부 `backend/` 기준)
- Interpreter: `/Users/Mung/dev/compa/backend/.venv/bin/python`
  (**워크트리엔 `.venv`가 없다.** main의 venv를 쓰되 cwd는 이 워크트리)
- Tests: `PYTHONPATH=. /Users/Mung/dev/compa/backend/.venv/bin/python -m pytest tests/ -q`
- Type: `PYTHONPATH=. /Users/Mung/dev/compa/backend/.venv/bin/python -m mypy --strict app/`
- **베이스라인: `488 passed, 1 skipped`** (A 랜딩 후 실측). 이 아래로 떨어지면 회귀
  - 그 1 skipped는 상시 스킵이다: `tests/scrapers/test_amoremall.py:160`
    (Playwright 네트워크). **건드리지 마라**
- 상시 데몬 worker/beat/api가 가동 중이다. **재시작하지 마라**

### ⚠️ 실제 PostgreSQL이 필요하다

**T9·T15는 live PG 대상이다** — `ON CONFLICT DO NOTHING RETURNING`과
`uq_sale_events_dedup` 유니크 인덱스의 실제 동작이 검증 대상이라 fake로는 못 잡는다.

- 이미 A에서 같은 문제를 푼 선례가 있다: `tests/core/test_database_event_loop.py`의
  skip 판정(실제 쿼리 1회 시도 + `engine.dispose()`)을 **그대로 재사용**하라
- **`try: ... except Exception: pytest.skip(...)` 같은 넓은 catch 금지** — 진짜 버그를
  환경 문제로 위장시킨다
- §8-3에 **어떤 테스트가 passed였고 어떤 게 skipped였는지 구분**해서 적어라.
  스킵을 통과로 보고하지 마라

---

## 1. Background

`collect_all_products`(Celery beat `collect-all-daily`)가 활성 상품 **339개 중 4개
(1.2%)만** 수집한다. `Product.name_kr.isnot(None)` 필터 때문인데, 상품 대부분은
브랜드 공홈에서 시딩돼 `name_en`만 있다(`name_en` 314 · `name_jp` 21 · `name_kr` 4).

필터만 지우면 **339 × 29 플랫폼 = 9,831 스크랩/일**이 된다. 그런데 공홈 스크래퍼는
`/products.json`으로 **브랜드 카탈로그를 한 번에** 받아온다 — 상품마다 부르는 건 같은
응답을 N번 다시 받는 것이다. 브랜드당 1콜, **총 26콜**로 211개 상품을 갱신할 수 있다.

**실측 (2026-08-08 09:45)**: 활성 339 · Path A 커버 **211/339 (62.2%)** ·
`sale_events` 156. 26개 브랜드 전부 `products.json` 응답 확인, platform 행도 26/26 존재.

---

## 2. Task 1 — 저장 헬퍼 추출 + dedup 수정 (`collector.py`)

**설계 §4.3 전문을 읽어라.** 요지:

```python
async def persist_events_for_product(
    db: AsyncSession, product: Product, platform: Platform, events: list[ScrapedEvent]
) -> int:
    """한 상품의 이벤트를 저장하고 **실제 insert된 행 수**를 반환한다."""
```

- **매칭하지 않는다.** 호출부가 확정한 product를 받는다
- `_save_events`의 저장 계약을 **전량 승계**한다 — 설계 §4.3의 승계 항목 표(9개 중 8개)
  를 그대로 지켜라. `confidence==0.0` 스킵 · `_classify_event_type` · `safe_url` ·
  `needs_review = confidence < 0.7` · `is_bundle` · `currency or "KRW"` ·
  `scraped_name`/`size_ml`/`raw_text` · `on_conflict_do_nothing`
- **바뀌는 건 하나뿐**: `_is_duplicate` precheck를 **제거**하고
  `INSERT ... ON CONFLICT DO NOTHING RETURNING id`로 실제 삽입 수를 센다.
  이유: DB 유니크 인덱스는 `COALESCE(size_ml, -1)`을 포함하는데 precheck의
  `_event_signature`엔 `size_ml`이 없어 **가격이 같은 다른 용량이 유실**된다
- `group_events_by_product_name(events) -> dict[str, list[ScrapedEvent]]` 순수 함수로
  분리 (이름 없는 이벤트 거르는 가드 포함)

### ⛔ 두 호출부의 계수 조건이 다르다 (감사 r6 P1)

| 호출부 | product id 수집 조건 |
|---|---|
| `_collect_platform` (사용자 검색) | **insert 수와 무관하게 항상 추가** (현행 `:300` 유지) |
| Path A (스윕) | `inserted > 0`인 상품만 `updated` 계수 |

양쪽에 같은 조건을 적용하면 **중복만 나온 상품이 검색 결과에서 사라진다.** T17이 이걸 잡는다.

---

## 3. Task 2 — 스윕 전용 엄격 매처 (`collector.py` private helper)

**설계 §4.2.1 전문을 읽어라.**

```python
async def _find_exact_for_sweep(
    db: AsyncSession, name: str, brand: str | None
) -> Product | None:
```

**`app/ai/matcher.py`에 넣지 마라.** `collector.py`의 private helper다.
`find_matching_product`는 **절대 쓰지 마라** — 그 함수는 브랜드 후보 휴리스틱과
**Claude API 호출**(`_ask_claude_for_match`)까지 간다. 카탈로그 2,388건을 스윕하면
일일 수천 건 LLM 호출이 나간다.

구현 순서를 고정한다(설계 §4.2.1):

1. `lower(Product.brand) == lower(brand)` AND `deleted_at IS NULL`로 DB 후보를 좁힌다
2. 후보를 **Python에서** `normalize_name(c.name_en) == normalize_name(name)` 비교
3. 0개 → `None` · 정확히 1개 → 그것 · **2개 이상 → `warning` 후 `None`**

`scalar_one_or_none()`으로 예외를 내지 마라 — 카탈로그 한 건 때문에 브랜드 전체가 죽는다.

---

## 4. Task 3 — `_collect_all` 재작성 (`collect.py`)

**설계 §4.2 의사코드와 §4.4·§5를 그대로 따라라.** 놓치기 쉬운 것 넷:

1. **대상 브랜드 0개면 `logger.error` + 즉시 반환**, 성공으로 보고하지 마라 (§4.2.-1)
2. **브랜드 예외 시 `await db.rollback()` 후 continue** — 없으면 세션이 실패 상태로
   고착돼 **이후 모든 브랜드가 연쇄 실패**한다 (§5.1.1)
3. **스크래퍼 실패는 예외로 안 온다** — `confidence=0.0` sentinel로 온다.
   이벤트 1건이고 `confidence==0.0`이거나 `confidence>0`이 0건이면 **fail로 세라** (§5.1)
4. **platform 행이 없으면 fail + warning** (§4.3.1)

반환값은 **insert가 1건 이상 발생한 상품 수**(`updated`). 로그는 §5.2 포맷:
`brands ok=N fail=M | products matched=211 updated=U skipped=2177 | events inserted=K`

세 카운터의 뜻이 다르다 — 2회차엔 `matched=211`이지만 `updated=0`이 정상이다.

---

## 5. Task 4 — 경계 warning + 설정 정정

- `backend/app/scrapers/brands/shopify.py`: `parse_products()` **호출 직전**에
  `payload["products"]` 길이가 **정확히 250이면 `logger.warning`** (§4.2.2).
  pagination이 없어 그 순간 카탈로그가 잘린 것이다
- `backend/.env.example`: `ENABLED_SCRAPERS=네이버쇼핑,Rakuten` → 현행 기본값
  `Sephora,Amazon US,Rakuten,brands`와 일치시켜라 (§4.2.-1).
  네이버쇼핑은 **API가 2026-07에 종료된 플랫폼**이다

---

## 6. Coding principles (project rules — non-negotiable)

- `requests` 금지 → `httpx.AsyncClient` · async 안에서 동기 호출 금지
- DB 스키마 직접 변경 금지 → Alembic (이번 작업은 스키마 무관)
- 예외 전파 금지, 에러 시 `raw_text` 보존 + `confidence=0`
- **`mypy --strict` 통과** — 신규 테스트도 타입 힌트
- 매직넘버 금지 — 모듈 레벨 `UPPER_SNAKE_CASE`
- 주석·docstring은 한국어, 식별자는 영어

---

## 7. Done criteria (checklist)

- [ ] Task 1: `persist_events_for_product` — 승계 항목 9개 중 8개 유지, precheck만 제거
- [ ] Task 2: `_find_exact_for_sweep` — `collector.py` private, LLM 호출 0, 3단계 순서
- [ ] Task 3: `_collect_all` 재작성 — 0개 가드 · rollback · sentinel fail · platform fail
- [ ] Task 4: 250 경계 warning + `.env.example` 정정
- [ ] `tests/tasks/test_collect.py` 신규 — **T1~T17 + T5b = 18케이스** (설계 §6)
- [ ] T9·T15는 live PG 테스트 (fake 금지)
- [ ] 전체 스위트 `488 passed, 1 skipped` + 신규 18
- [ ] `mypy --strict app/` clean
- [ ] §8-3에 테스트별 passed/skipped 구분 기록
- [ ] Self-score §8-7 (감점 사유 먼저)
- [ ] **커밋하지 않음**

### Acceptance rubric (실행 전 고정)

| Dimension | What 5 means | Gate |
|-----------|--------------|------|
| **No LLM in sweep** | 스윕 경로에서 `find_matching_product`·`_ask_claude_for_match`가 **한 번도** 호출되지 않음. T8이 이를 실제로 감시 | **5** |
| **Silent-failure coverage** | 조용한 실패 6종(0개 대상·sentinel·platform 없음·rollback 누락·다중 후보·용량 유실)이 전부 테스트로 잡힘 | **5** |
| **Contract preservation** | `_save_events`의 저장 필드 8종 승계, `_collect_platform` 반환 계약 불변(T10·T17) | 4+ |
| **Correctness** | 설계 §4·§5와 일치, 기각된 대안(LLM 매처·`create_missing` 플래그) 미혼입 | 4+ |
| **Scope containment** | §7 후속 항목(pagination·정본 카탈로그·정크 정리·검색 플랫폼)에 손대지 않음 | 4+ |

앞의 두 차원 게이트가 5인 이유: 이 설계의 위험은 "틀리게 동작"이 아니라
**"아무것도 안 하면서 정상으로 보임"**과 **"조용히 비용이 나감"**에 몰려 있다.
둘 다 결과만 봐서는 안 보인다.

어느 차원이든 게이트 미달 = 미완료. 보고 전에 재작업하라.

---

## 8. Executor response (executor writes here)

> §7 항목을 채우고 상태줄을 `검토대기 / review-pending`으로. **커밋하지 마라.**

### 8-1. Files changed
_(write here)_

### 8-2. New tests
_(write here)_

### 8-3. Final test result
_(write here — 테스트별 passed/skipped 구분 필수)_

### 8-4. Consistency scan / findings
_(write here)_

### 8-5. Backward-compat check
_(write here — `_collect_platform` 사용자 검색 경로 불변 확인)_

### 8-6. Blocked / judgment calls
_(write here — 없으면 "none")_

### 8-7. Rubric self-score
_(차원별로 감점 사유 먼저, 그 다음 점수)_

---

## 9. Review log (author/reviewer writes after verifying)

**Reviewed:** _(YYYY-MM-DD)_ | **Verdict:** _(approved / changes requested)_

### Verified directly
_(diff 정독, 리뷰어 직접 실행 테스트, 본문 판독, 리버트 실증 등)_

### Notable / beyond spec
_(좋은 판단, 또는 확인이 필요했던 범위 이탈)_

### Follow-up
_(커밋 해시 · 머지 · 재시작 · 라이브 스모크)_
