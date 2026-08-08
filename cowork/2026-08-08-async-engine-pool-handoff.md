# Codex Handoff — 2026-08-08 · asyncio 엔진 풀 (A)

> **상태(Status):** `대기중 / pending`
> _(Executor: 시작 시 `진행중 / in-progress`, 완료 시 `검토대기 / review-pending`.
>  `완료 / done`은 리뷰어만 커밋 후 설정.)_
>
> **시작 기록(Started by):** `session=2c299c4f-c3a2-492e-83a9-a24fd2b61acf machine=mac-studio started=2026-08-08T08:40:31-0700`
>
> **작성자(Author):** Claude Opus 5 (설계·리뷰) → **수행자(Executor):** Codex CLI
> **작업명(Task):** `app/core/database.py`의 async 엔진을 `NullPool`로 전환 + 이벤트 루프 회귀 테스트 신규
> **설계 근거(Design basis):** `docs/design-async-engine-pool-2026-08-08.md` — **반드시 먼저 읽을 것.**
> 적대적 감사 6라운드를 거쳐 지적 44건 중 38건 반영된 문서다. 특히 **§4(설계)·§6(테스트 계획)**이
> 이 핸드오프의 정본이며, 아래 내용과 어긋나면 설계문서가 우선한다.
> **범위(Scope):** in — `backend/app/core/database.py` 1줄 + `backend/tests/core/test_database_event_loop.py` 신규(T1~T4).
> out — `collector.py`의 `_BROWSER_SEMAPHORE` 실제 수정(설계 §8 후속), 수집 스코프(별도 문서 B),
> CI 워크플로 수정, 커넥션 풀 파라미터 튜닝, 엔진 분리.

---

## 0. How to use this document (Executor, read first)

너에게는 이 프로젝트의 맥락도 이전 대화도 없다. 아래 내용만 신뢰하라.

- **하지 마라:** 범위 밖 리팩터 · 라이브/프로덕션 진입점 실행 · 프로덕션 설정 변경 ·
  데이터 대량 편집 · **커밋**(워킹트리만 남기고 리뷰어에게 넘긴다) · main 머지 ·
  worker/beat/api 재시작 · `.env` 생성·수정
- **항상:** 각 Task 후 테스트 실행 → 통과 확인 → 다음 Task. 작업 내용을 §8에 기록.
  시작·완료 시 맨 위 상태줄 변경
- **확신 없으면:** 추측하지 마라. 멈추고 §8에 질문을 남겨라

### Execution environment

- **cwd: `backend/`** (워크트리 루트가 아니다. 파일 경로는 전부 `backend/` 기준)
- Interpreter: `/Users/Mung/dev/compa/backend/.venv/bin/python`
  — **워크트리에는 `.venv`가 없다.** main 체크아웃의 venv를 쓰되 cwd는 이 워크트리로 둔다.
  이 조합으로 2026-08-08 베이스라인 실측 완료
- Tests: `PYTHONPATH=. /Users/Mung/dev/compa/backend/.venv/bin/python -m pytest tests/ -q`
- Type check: `PYTHONPATH=. /Users/Mung/dev/compa/backend/.venv/bin/python -m mypy --strict app/`
- **현재 테스트 베이스라인: `484 passed, 1 skipped` (1.71s).** 이 아래로 떨어지면 회귀다.
  - 그 **1 skipped는 원래 그렇다**: `tests/scrapers/test_amoremall.py:160`
    (*"실제 Playwright/네트워크 호출 — CI에서 스킵"*). **건드리지 마라. 정확히 이대로 유지.**
- 상시 데몬: compa는 **launchd로 worker/beat/api 3개가 상시 가동 중**이다
  (`com.compa.worker` / `.beat` / `.api`). **재시작하지 마라** — 배포 게이트는 설계 §7.0 참조.
  (참고: `cowork/CONVENTIONS.md`의 "상시 데몬 없음"은 낡은 기술이다. 이 핸드오프가 우선한다)

### ⚠️ 이 작업의 특수 조건 — 실제 PostgreSQL이 필요하다

T1/T3은 **살아있는 로컬 PostgreSQL**에 붙는다(`postgresql+asyncpg://compa:compa@localhost:5432/compa`).

- 네 샌드박스에서 DB에 못 닿으면 **T1/T3은 skip으로 나올 수 있다.** 그건 예상된 상황이다
- **그 경우 테스트를 "고치지" 마라.** 특히 **`try: ... except Exception: pytest.skip(...)`
  같은 넓은 catch로 감싸지 마라** — 그 패턴은 진짜 코드 버그를 "환경 문제"로 위장시킨다
  (과거 실증 사례 있음). 스킵 조건은 설계 §6이 지정한 대로 **판정 쿼리 성공 여부**로만 둔다
- §8-3에 **"내 환경에서 T1/T3이 passed였는지 skipped였는지"를 정확히 구분해서 적어라.**
  스킵을 통과로 보고하지 마라. 리뷰어가 DB 있는 환경에서 직접 재실행해 최종 판정한다
- 참고: 이 스위트에는 이미 live PG에 의존하면서 skip 가드가 없는 테스트가 4개 있다
  (`test_sale_windows` / `test_match_products` / `test_feedback` / `test_admin`).
  **이건 이 작업 이전부터 있던 레포 상태이고 범위 밖이다.** 고치지 마라.
  베이스라인 `484 passed`는 **PG가 살아있는 로컬 수치**다

---

## 1. Background (why this work)

compa는 화장품 가격 추적 서비스다. Celery(worker + beat)가 수집·분류·소셜 태스크를 돌린다.

**2026-08-05 19:15부터 사흘째 Celery 파이프라인이 84% 실패 중이다** — `worker.err.log`
전수 집계로 48 성공 / 259 실패(16% 성공률), `another operation is in progress` 1,000회.

근본 원인: `app/core/database.py:8`의 모듈 레벨 async 엔진이 기본
`AsyncAdaptedQueuePool`을 쓴다. 그런데 Celery 태스크는 매번 `asyncio.run()`으로 **새
이벤트 루프**를 만든다(호출지점 11곳). `asyncio.run()`이 끝나면 루프는 닫히지만 asyncpg
커넥션은 풀에 남고, 그 커넥션의 프로토콜 객체는 **닫힌 루프에 묶여 있다.** 다음 태스크가
그 커넥션을 체크아웃하면 터진다.

프로덕션과 동일 조건(같은 프로세스, 연속 `asyncio.run()`)으로 재현했다:

```
run #1: OK
run #2: RuntimeError: Task ... attached to a different loop
run #3: InterfaceError: cannot perform operation: another operation is in progress
run #4: InterfaceError: ...
```

**첫 건만 성공하고 이후 실패** — 실제 실패 분포(prefork 프로세스당 첫 태스크만 통과)와
정확히 일치한다. `poolclass=NullPool`을 적용한 같은 스크립트는 **6/6 성공**했다.

---

## 2. Task 1 — `NullPool` 적용 (P0)

### 진단 / Diagnosis (proven, not asserted)

`backend/app/core/database.py:8`:

```python
engine = create_async_engine(settings.database_url, echo=False)
```

`poolclass` 미지정 → SQLAlchemy 기본 `AsyncAdaptedQueuePool`. 이 풀이 루프 경계를 넘어
커넥션을 재사용하는 것이 위 실패의 원인이다. 레포 전체에서 `create_async_engine`는
**이 1곳뿐**이고 `NullPool`·`poolclass`·`pool_size` 사용처는 **없다**.

### 수정 방법 / How to fix

설계 §4 그대로:

```python
from sqlalchemy.pool import NullPool

engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)
```

`NullPool`은 세션마다 커넥션을 새로 열고 반납 시 닫는다 → 풀에 남는 커넥션이 없으므로
루프 간 재사용이 **구조적으로 불가능**하다.

### 주의·제약 / Constraints

- **`AsyncSessionLocal`·`get_db`의 시그니처와 동작은 그대로 둔다.** import 경로도 불변
- 다른 파라미터(`pool_size`, `max_overflow`, `pool_pre_ping` 등)를 **추가하지 마라** —
  `NullPool`과 함께 쓰면 SQLAlchemy가 에러를 낸다. 설계에서 명시적으로 기각한 대안이다
- 엔진을 Celery용/API용으로 **분리하지 마라** — 설계 §5 대안표에서 기각됐다
  (무증상 재발 모드를 갖는다는 것이 기각 사유)
- 이 변경이 커넥션 상한을 없앤다는 점은 설계 §5·§5.1에 이미 분석·기록돼 있다.
  **네가 다시 판단하거나 완화 장치를 추가할 필요 없다**

### 필수 테스트 / Required tests

Task 2에서 한꺼번에 작성한다.

---

## 3. Task 2 — 이벤트 루프 회귀 테스트 신규 (P0)

`backend/tests/core/test_database_event_loop.py` 신규 작성. **설계 §6이 정본이다** —
아래는 요약이니 반드시 §6 원문(226~289행)을 읽고 그대로 구현하라.

| # | 케이스 | 반드시 지킬 것 |
|---|---|---|
| **T1** | 같은 프로세스에서 `asyncio.run()`을 **3회 연속** 호출, 매 회차가 전부 성공 | **1회만 도는 테스트는 이 버그를 절대 못 잡는다.** 각 회차는 `AsyncSessionLocal` + ORM 쿼리(`select(Product).limit(1)`) + `commit()`까지 포함 — `SELECT 1`은 체크아웃만 보고 ORM 트랜잭션 경로를 안 봐서 불충분(감사 r1) |
| **T2** | `engine.pool`이 `NullPool` 인스턴스인지 | 누가 풀을 되돌리면 즉시 실패하는 가드 |
| **T3** | `classify_pending(limit=0)`을 같은 프로세스에서 **2회 연속** 호출, 전부 성공 | T1은 `AsyncSessionLocal`만 돌려서 실제 실패 경로인 **동기 래퍼 → `asyncio.run()`**(`app/tasks/classify.py:13`)을 안 덮는다 |
| **T4** | `len(set(get_enabled_scrapers()) & set(_BROWSER_SCRAPERS)) < 5` | §3.1 잠복 버그(`_BROWSER_SEMAPHORE` 루프 고착)의 **발화 조건 트립와이어**. 버그를 고치는 게 아니라 설정이 넓어지는 순간을 실패로 드러내는 것 |

### ⛔ T3에서 부작용 있는 래퍼를 부르지 마라

**회귀 테스트가 운영 데이터를 지우면 안 된다.** 실측 확인된 지뢰:

- `purge_expired_social_posts()` — **하드 삭제** (`app/tasks/reddit_signals.py:140`)
- `classify_pending()` — 기본 `limit=50`으로 실제 `SaleEvent`를 수정·commit하고
  Anthropic API 호출까지 간다 (`app/tasks/classify.py:47`)
- `run_collection_slow()` — 실제 스크래퍼 팬아웃

→ **반드시 `classify_pending(limit=0)`**을 쓴다. 조회 0건이라 부작용이 없으면서
`동기 래퍼 → asyncio.run() → AsyncSessionLocal → 쿼리` 실패 경로는 그대로 태운다.
무해함과 재현성을 동시에 만족하는 유일한 지점이다.

### T1/T3의 DB 스킵 판정 — 설계 §6이 지정한 방식 그대로

- `pytest.mark.skipif`로 두되 **스킵 사유 문자열에 `requires live PG`를 명시**
- **판정 술어는 collection time에 안전한 동기 함수**여야 한다. `skipif` 안에서 async
  엔진을 만들면 import 시점 부작용이 생긴다. 판정 헬퍼는 **이 테스트 파일 안에** 둔다
  (새 모듈 만들지 마라)
- **포트 열림 확인만으로는 부족하다.** 소켓 연결은 credential·스키마·마이그레이션 상태를
  못 본다 → DB 준비 문제가 설계 변경 실패로 오인된다. T1이 `select(Product).limit(1) +
  commit()`까지 하므로 판정도 **"그 쿼리가 실제로 되는가"**여야 한다. 모듈 로드 시
  `asyncio.run()`으로 동일 쿼리를 1회 시도해 성공한 경우에만 실행하고, 실패 사유
  (`OperationalError` 메시지 등)를 스킵 메시지에 담는다
- **판정 쿼리 직후 반드시 `await engine.dispose()`** — 이 판정이 남긴 커넥션이 풀에
  남으면 바로 그 상태가 T1이 검사하려는 "루프 간 재사용"을 오염시킨다. 판정이 테스트를
  무의미하게 만드는 자기부정을 피해야 한다

---

## 5. Coding principles (project rules — non-negotiable)

`CLAUDE.md`에서:

- `requests` 금지 → `httpx.AsyncClient`
- async 라우트 안에서 동기 호출 금지 (블로킹은 `asyncio.to_thread`)
- DB 스키마 직접 변경 금지 → Alembic 필수 (이번 작업은 스키마 무관)
- 에러 발생 시 `raw_text` 보존 + `confidence=0`, 예외 전파 금지
- **`mypy --strict` 통과** — 신규 테스트 파일도 타입 힌트를 붙일 것
- `.env` 커밋 금지 / API 키 하드코딩 금지
- 매직넘버 금지 — 상수는 모듈 레벨 `UPPER_SNAKE_CASE`로
- 주석·docstring은 **한국어**로 쓰되(이 레포 관행), 코드 식별자는 영어

---

## 6. Done criteria (checklist)

- [ ] Task 1: `database.py`에 `poolclass=NullPool` 적용, 다른 풀 파라미터 추가 없음
- [ ] Task 2: `tests/core/test_database_event_loop.py` 신규 — T1~T4 전부 구현
- [ ] T3가 `classify_pending(limit=0)`을 쓴다 (부작용 있는 래퍼 사용 안 함)
- [ ] T1/T3의 스킵 판정이 **실제 쿼리 성공 여부** 기준이고, 판정 후 `engine.dispose()` 호출
- [ ] 넓은 `except Exception: pytest.skip(...)` 패턴 **사용 안 함**
- [ ] 전체 스위트가 베이스라인 이상 (`484 passed, 1 skipped` + 신규 테스트 수)
- [ ] `mypy --strict app/` clean
- [ ] §8-3에 T1/T3의 passed/skipped를 **구분해서** 기록
- [ ] Self-score 표 §8-7 작성 (감점 사유 먼저, 그 다음 점수)
- [ ] **커밋하지 않음** (워킹트리 변경만)

### Acceptance rubric (실행 전 고정 — 설계문서 기준)

| Dimension | What 5 means | Gate |
|-----------|--------------|------|
| **Correctness** | `NullPool` 적용이 설계 §4와 정확히 일치하고, 다른 풀 파라미터·엔진 분리 등 기각된 대안이 섞이지 않음 | 4+ |
| **Test fidelity** | T1이 3회 연속·ORM+commit까지, T3이 `limit=0` 동기 래퍼 2회 연속을 실제로 태움. 1회만 도는 테스트나 부작용 래퍼가 없음 | **5** |
| **Skip discipline** | 스킵 판정이 실제 쿼리 기준 + `dispose()` 호출. 넓은 catch로 버그를 은폐하지 않음. 스킵을 통과로 보고하지 않음 | 4+ |
| **Scope containment** | `collector.py`·CI·수집 스코프 등 §8 후속 항목에 손대지 않음 | 4+ |

**Test fidelity의 게이트가 5인 이유**: 이 테스트가 약하면 P0가 조용히 되돌아와도 아무도
모른다. 1회만 도는 T1은 이 버그에 대해 **항상 통과**한다 — 없는 것보다 나쁘다.

어느 차원이든 게이트 미달 = 미완료. 보고 전에 재작업하라.

---

## 7. What the executor reports (fill §8 below)

1. 변경 파일 + 각 한 줄 요약
2. 신규 테스트 파일 + 테스트 개수
3. 최종 테스트 결과 (passed/skipped) — **T1/T3은 개별로 구분해서**
4. 일관성 스캔/grep 결과 + 처리 방법
5. 하위 호환 확인 결과
6. 막힌 것 / 판단으로 처리한 것
7. Rubric self-score — 차원별로 **감점 사유 먼저**, 그 다음 1-5점

---

## 8. Executor response (executor writes here)

> §7의 7개 항목을 채운 뒤 맨 위 상태줄을 `검토대기 / review-pending`으로 바꿔라.
> 워킹트리 변경만 남기고 **커밋하지 마라.**

### 8-1. Files changed
_(write here)_

### 8-2. New tests
_(write here)_

### 8-3. Final test result
_(write here — T1/T3 passed vs skipped 구분 필수)_

### 8-4. Consistency scan / findings
_(write here)_

### 8-5. Backward-compat check
_(write here)_

### 8-6. Blocked / judgment calls
_(write here — 없으면 "none")_

### 8-7. Rubric self-score
_(§6 rubric의 차원별로: 감점 사유 먼저, 그 다음 점수)_

---

## 9. Review log (author/reviewer writes after verifying)

**Reviewed:** _(YYYY-MM-DD)_ | **Verdict:** _(approved / changes requested)_

### Verified directly
_(diff 정독, 리뷰어가 직접 실행한 테스트, 테스트 본문 판독 등)_

### Notable / beyond spec
_(executor의 좋은 판단, 또는 확인이 필요했던 범위 이탈)_

### Follow-up
_(커밋 해시 · 프로세스 재시작 · 다음 단계)_
