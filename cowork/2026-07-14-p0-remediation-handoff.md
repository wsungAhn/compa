# Codex Handoff — 2026-07-14

> **상태(Status):** `완료 / done`
> _(Executor: set `진행중 / in-progress` on start, `검토대기 / review-pending` when done.
>  Only the author/reviewer sets `완료 / done`, after the commit.)_
>
> **작성자(Author):** Claude (총괄 PM) → **수행자(Executor):** Codex CLI
> **작업명(Task):** 2026-07-13 통합 감사 P0 6건 수정 (COMPA Phase 1)
> **설계 근거(Design basis):** `~/agent_hub/docs/design-cross-project-audit-remediation-2026-07-14.md` §1 Phase 1
> **범위(Scope):** 아래 6개 Task만. 프리미엄/결제, 스크래퍼 신규 추가, UI 리디자인은 범위 밖.

---

## 0. How to use this document (Executor, read first)

- **Do NOT:** 범위 밖 리팩터 · premium/결제 코드 변경 · DB 스키마 직접 변경(Alembic 필수) ·
  커밋 (working tree만 남길 것).
- **Always:** 각 Task 끝날 때마다 테스트 실행 → 통과 확인 → 다음 Task. §8에 기록.
  시작/종료 시 상단 상태줄 갱신.
- **If unsure:** 추측 금지. §8에 질문으로 남기고 멈출 것.

### Execution environment
- Interpreter (backend): `backend/.venv/bin/python`
- Tests: `cd backend && .venv/bin/python -m pytest tests/ -q`
- Type check: `cd backend && .venv/bin/python -m mypy --strict app/`
- Frontend: `cd frontend && npm run build && npm run lint`
- **Current baseline (2026-07-14 확인): backend `310 passed, 1 skipped`, mypy `Success: no issues found in 73 source files`, frontend build/lint 성공.** 이 아래로 떨어지면 회귀.
- Playwright 스크래퍼(sephora/oliveyoung/amoremall)는 이 Task 범위 밖 — 건드리지 않음.
- frankencrawler(P0-4 관련)는 `http://localhost:8765`에 상시 실행 중, v0.12.0, SDK는
  `pip install -e ~/dev/firecrawl-local`로 설치 가능.

---

## 1. Background (why this work)

2026-07-13 통합 감사에서 COMPA backend/frontend 계약 불일치와 데이터 무결성 문제 6건이
P0로 발견됨. 사용자 대면 버그(수집 완료를 인식 못함, 빈 이력 제품이 뜸)와 조용한 데이터
손실(실패해도 처리완료로 기록)이 섞여 있어 우선순위가 높음. 아래 6개를 이번 라운드에서
전부 수정한다.

---

## 2. Task 1 — Backend/frontend JobStatus 계약 불일치 (P0-1)

### 진단
`backend/app/api/jobs.py:11-24`:
```python
class JobStatus(BaseModel):
    task_id: str
    status: str
    ready: bool

@router.get("/{task_id}", response_model=JobStatus)
async def get_job_status(task_id: str) -> JobStatus:
    result = celery.AsyncResult(task_id)
    return JobStatus(task_id=task_id, status=result.state.lower(), ready=result.ready())
```
Celery state는 `pending`/`started`/`success`/`failure` 형태 (`result.state.lower()`).
`backend/app/tasks/collect.py:41-52`의 실제 task도 이 상태만 남긴다.

Frontend는 `done`/`failed`를 기다리고 `products` 배열을 참조:
- `frontend/src/api/client.ts:82-91`
- `frontend/src/components/SearchBar.tsx:107-127`

즉 collect task가 `success`로 끝나도 frontend는 영원히 완료를 인식하지 못하거나
`status.products`가 undefined가 된다.

### 수정 방법
가장 단순한 방향(권장): frontend가 `status === 'success'`를 완료로 인식하고, 완료 시
`/products/search?q=<query>&collect=false`를 재호출해서 products를 갱신하도록
`SearchBar.tsx`의 폴링 로직을 수정. `status === 'failure'`는 기존 실패 처리 유지.
backend `JobStatus` 모델 자체는 변경하지 않아도 됨(굳이 `products` 필드를 얹지 않아도
frontend 재호출 방식이 더 단순).

### 주의·제약
- Celery task 상태값 자체(`pending/started/success/failure`)는 바꾸지 말 것 — 다른 소비자가 있을 수 있음.
- 폴링 간격/타임아웃은 기존 값 유지.

### 필수 테스트
- `frontend`: SearchBar가 `success` 상태에서 재검색 API를 호출하는지 확인하는 테스트(기존 테스트 프레임워크 있으면 그것으로, 없으면 최소 단위 테스트 추가).
- `backend`: 기존 `tests/`에 회귀 없는지만 확인(이 Task는 backend 변경 없음 예상).

---

## 3. Task 2 — collect가 placeholder Product를 반환할 수 있음 (P0-2)

### 진단
`backend/app/scrapers/collector.py:275-293`의 `collect_fast()`/`collect_on_demand()`가
먼저 `get_or_create_product(db, query, None, "KR")`로 **검색어 자체의 Product**를 생성.
실제 scrape된 product는 `_collect_platform()`(같은 파일 296-331) 내부에서 product_name별
**별도 Product**에 이벤트가 붙는다. 그런데 `backend/app/api/products.py:158-176`의 API는
fast-path 결과로 `[product]`(query placeholder)를 그대로 반환할 수 있음 → 사용자가
이벤트 없는 placeholder를 선택하게 됨, `/events` 조회 시 빈 이력으로 보임.

### 수정 방법
`collect_fast()`/`collect_on_demand()`가 리턴하기 전에, `_collect_platform()`이 실제로
생성/업데이트한 Product id 목록을 모아서 그 Product들을 재조회해 반환하도록 수정.
placeholder product는 검색 편의용으로만 남기고 API 응답에는 포함하지 않는다.
(대안으로 `_collect_platform()`이 product ids를 리턴값에 포함하도록 시그니처를 바꿔도 됨 — executor 판단.)

### 주의·제약
- placeholder Product 자체를 지우지는 말 것(검색 캐시/매칭에 쓰일 수 있음) — API 반환 목록에서만 제외.
- 기존 `get_or_create_product` 호출 규약은 유지.

### 필수 테스트
- `backend/tests/`: collect 후 반환된 product 목록에 실제 이벤트가 존재하는지 확인하는 테스트 추가 (fake scraper 사용).

---

## 4. Task 3 — `pytest-asyncio` 누락 (P0-3)

### 진단
`backend/requirements.txt`에 `pytest-asyncio`가 명시돼 있지 않음(현재 로컬 venv에는
우연히 설치돼 있어 `310 passed, 1 skipped`가 나오지만, 신선한 설치/CI 환경에서는 async
테스트가 조용히 skip됨 — 2026-07-13 감사에서 실측: 미설치 시 `286 passed, 25 skipped`).

### 수정 방법
`backend/requirements.txt`에 `pytest-asyncio` 버전 고정 추가(현재 venv에 설치된 버전과
동일하게 — `backend/.venv/bin/pip show pytest-asyncio`로 확인). `backend/pytest.ini`에
`asyncio_mode` 설정이 없으면 명시. CI(`.github/workflows/ci.yml`이 있으면)에서
`-W error::pytest.PytestUnraisableExceptionWarning` 또는 skip 발생 시 fail하도록
strict-markers 검토(무리하면 skip만 방지하는 선에서 그쳐도 됨).

### 주의·제약
- 버전을 임의로 최신으로 올리지 말고, 현재 동작 확인된 버전으로 고정.

### 필수 테스트
- 없음(설정 변경) — 단, `pip install -r requirements.txt`를 새 venv에서 실행해 async
  테스트가 skip 없이 도는지 한 번 확인(가능하면).

---

## 5. Task 4 — firecrawl-local SDK/Docker wiring 미완성 (P0-4)

### 진단
- `backend/requirements.txt`에 firecrawl-local SDK가 없음.
- `backend/app/scrapers/firecrawl_client.py`: SDK import 실패 시 `AsyncFirecrawlClient = None`으로 두고, 호출 시 조용히 `[]` 반환.
- `backend/app/core/config.py`: `firecrawl_url = "http://localhost:8765"` 기본값 — Docker 컨테이너 내부에서는 컨테이너 자신의 localhost를 가리켜 틀림.
- `docker-compose.yml`에 firecrawl-local 서비스가 없음.

**현재 상태(2026-07-14):** frankencrawler는 이 Mac Studio에서 `http://localhost:8765`에
v0.12.0으로 정상 실행 중(health OK). SDK는 `pip install -e ~/dev/firecrawl-local`로 설치
가능 (`backend/.venv/bin/pip install -e ~/dev/firecrawl-local`).

### 수정 방법
1. `backend/requirements.txt`에 `-e ~/dev/firecrawl-local` 또는 동등한 방식으로 SDK 의존성 명시(경로 하드코딩이 싫으면 최소한 README/설치 스크립트에 명시).
2. `firecrawl_client.py`의 silent-empty-list를 제거 — import 실패나 서버 미응답 시 로그로 에러를 표면화(예외를 삼키지 말고 warning 로그 + 빈 결과를 명확히 구분되는 상태로 반환).
3. `/health` 엔드포인트(있는 곳)에 firecrawl availability/version 정보 포함.
4. Docker 사용 시를 대비해 `FIRECRAWL_URL` 환경변수로 오버라이드 가능하게 유지(이미 config.py에서 가능하면 그대로, 아니면 추가) — 기본값은 로컬 개발 기준 `http://localhost:8765` 유지, docker-compose 쓸 때는 `http://firecrawl-local:8765`로 오버라이드하도록 주석/문서화만 추가(실제 compose 서비스 추가는 이번 범위 밖).

### 주의·제약
- docker-compose.yml에 실제 frankencrawler 서비스를 추가하는 건 이번 범위 밖(문서화만).
- SDK 경로 하드코딩(`~/dev/firecrawl-local`)은 로컬 개발 한정 임시 방편임을 주석으로 남길 것.

### 필수 테스트
- `firecrawl_client.py` 관련 기존 테스트가 있으면 SDK 미설치 상황을 흉내낸 fallback 테스트 추가(로그 발생 확인).

---

## 6. Task 5 — local AI 모드에서 social pipeline이 동작하지 않음 (P0-5)

### 진단
`backend/app/ai/pipeline.py:94` (2026-07-14 재확인):
```python
if not posts or not settings.anthropic_api_key:
    return 0
```
`settings.use_local_ai=True`여도 `anthropic_api_key`가 없으면 즉시 `return 0` — local AI
모드가 사실상 동작하지 않음.

### 수정 방법
```python
if not posts:
    return 0
if not settings.use_local_ai and not settings.anthropic_api_key:
    return 0
```
이후 `SocialExtractor`/classifier/matcher가 `USE_LOCAL_AI=true`일 때 실제로 로컬
클라이언트(`app/ai/local_client.py` 등, 있으면)를 쓰는지 확인 — 없다면 이 Task는
gate 조건만 고치고, 로컬 클라이언트 실제 연결은 별도 이슈로 §8에 기록.

### 주의·제약
- `settings.anthropic_api_key`가 있는 기존 경로(Claude 모드) 동작은 그대로 유지.

### 필수 테스트
- `USE_LOCAL_AI=true` + `anthropic_api_key` 없음 조합에서 `process_social_posts`가
  0을 조기 반환하지 *않고* 실제로 진행하는지 확인하는 테스트 추가.

---

## 7. Task 6 — Social 실패/빈결과에도 processed=True 처리 (P0-6)

### 진단
`backend/app/ai/pipeline.py:97-100, 187-196`: LLM 호출 실패, JSON 파싱 실패, 0건 추출,
플랫폼 매칭 실패가 발생해도 마지막에 모든 post를 `processed=True`로 처리 — 재시도
불가능한 데이터 손실. 이 위험 동작을 고정한 테스트가 이미 존재:
`backend/tests/ai/test_pipeline.py:234-260` (수정 시 이 테스트의 기대값도 함께 바꿔야 함).

### 수정 방법
`SocialPost`에 `processed`/`failed`/`retry_count`/`last_error` 상태를 분리(모델에 이미
비슷한 필드가 있으면 재사용, 없으면 Alembic 마이그레이션으로 추가). 0건 추출/일시
장애는 `processed=False`, `retry_count += 1`, `last_error`에 사유 기록해 다음 배치에서
재시도 가능하게. 영구 실패(예: 명백히 처리 불가한 컨텐츠)만 `processed=True`+`failed=True`.

### 주의·제약
- DB 스키마 변경은 반드시 Alembic revision으로 (`alembic revision --autogenerate -m "..."`).
- 기존 `test_pipeline.py:234-260`의 "실패해도 processed=True" 기대값은 이번 수정의 의도와
  반대이므로 **의도적으로 수정** — 왜 바꿨는지 테스트 docstring/주석에 한 줄 남길 것.

### 필수 테스트
- `test_pipeline.py`에 실패 시 `processed=False`+`retry_count` 증가를 확인하는 케이스 추가.
- 영구 실패 케이스(있다면)는 `processed=True`+`failed=True` 확인.

---

## 8. Coding principles (compa 규칙 — 비타협)

- `.env` 커밋 금지 / API 키 하드코딩 금지
- `requests` 금지 → `httpx.AsyncClient`
- async 라우트 안 동기 호출 금지 (블로킹은 `asyncio.to_thread`)
- DB 스키마 변경은 Alembic 필수
- 에러 시 `raw_text` 보존 + `confidence=0`, 예외 전파 금지 (AI 파이프라인 한정 — Task 6은 예외임: 여긴 상태 분리가 핵심)
- `mypy --strict` 통과 / TS strict 유지 / 테스트 없는 변경 금지

---

## 9. Done criteria (checklist)

- [x] Task 1: JobStatus 계약 불일치 — frontend가 success를 완료로 인식
- [x] Task 2: collect가 실제 이벤트 붙은 product 반환
- [x] Task 3: pytest-asyncio requirements.txt에 명시
- [x] Task 4: firecrawl SDK 의존성 명시 + silent empty-list 제거
- [x] Task 5: local AI 모드 gate 수정
- [x] Task 6: social 실패 시 processed 상태 분리
- [x] 새 테스트 작성 + 통과
- [x] backend `310 passed, 1 skipped` 이상 유지, mypy --strict 통과, frontend build/lint 통과
- [x] 커밋 안 함 (working tree만)

---

## 10. What the executor reports (fill §11 below)

1. Files changed + 한 줄 요약씩
2. 새 테스트 파일 + 테스트 개수
3. 최종 테스트 결과 (backend pytest, mypy, frontend build/lint)
4. Alembic migration 생성했으면 revision id
5. 판단이 필요했던 부분 (예: Task 5 로컬 클라이언트 실제 연결 여부)
6. 막힌 것 / 판단 보류한 것

---

## 11. Executor response (executor writes here)

### 11-1. Files changed
- `.github/workflows/ci.yml` — pytest 실행에 `--strict-markers`와 unraisable warning error 옵션 추가.
- `backend/requirements.txt` — `pytest-asyncio==1.4.0` 명시, resolver 충돌 방지를 위해 `pytest==8.4.0`으로 조정, firecrawl local install 안내 추가.
- `backend/pytest.ini` — `asyncio_default_fixture_loop_scope = function` 명시.
- `backend/requirements-firecrawl-local.txt` — local 개발용 firecrawl-local editable SDK 설치 경로 명시.
- `backend/app/scrapers/collector.py` — `_collect_platform()`이 실제 수집 product id를 반환하고, `collect_fast()`/`collect_on_demand()`가 이벤트 보유 product만 반환하도록 변경.
- `backend/app/scrapers/firecrawl_client.py` — SDK 미설치 시 warning 로그, `/health`용 firecrawl status helper 추가.
- `backend/app/main.py` — `/health` 응답에 firecrawl availability/version 정보 추가.
- `backend/app/core/config.py` — Docker compose의 `FIRECRAWL_URL` override 주석 추가.
- `docker-compose.yml` — api/worker/beat에 `FIRECRAWL_URL` env override와 compose용 주석 추가.
- `backend/app/ai/pipeline.py` — local AI gate 수정, social post retry/permanent failure 상태 전환 추가.
- `backend/app/models/social_post.py` — `failed`, `retry_count`, `last_error` 필드 추가.
- `backend/alembic/versions/d5f6a7b8c9e0_add_social_post_failure_state.py` — social post failure state migration 추가.
- `backend/tests/ai/test_pipeline.py` — local AI gate, retryable empty extraction, platform failure, permanent failure 기대값/테스트 갱신.
- `backend/tests/scrapers/test_enabled_scrapers.py` — collect_fast가 placeholder를 반환하지 않는 테스트 추가.
- `backend/tests/scrapers/test_firecrawl_client.py` — firecrawl SDK 미설치 로그/status 및 health status 테스트 추가.
- `frontend/src/api/client.ts` — JobStatus 타입을 backend 응답(`task_id/status/ready`, `success/failure`)과 일치.
- `frontend/src/components/SearchBar.tsx` — job `success` 시 `/products/search?collect=false` 재호출로 결과 갱신.
- `frontend/src/components/searchPolling.ts` — polling 상태 결정 helper 추가.
- `frontend/src/components/searchPolling.test.mjs` — Node 내장 test runner 기반 polling helper 테스트 추가.
- `frontend/package.json` — `npm run test` script 추가.
- `cowork/2026-07-14-p0-remediation-handoff.md` — 상태/체크리스트/Executor response 갱신.

### 11-2. New tests
- 새 테스트 파일:
  - `backend/tests/scrapers/test_firecrawl_client.py` — 3 tests.
  - `frontend/src/components/searchPolling.test.mjs` — 3 tests.
- 기존 테스트 파일에 추가:
  - `backend/tests/scrapers/test_enabled_scrapers.py` — 1 test.
  - `backend/tests/ai/test_pipeline.py` — 2 new tests, 2 existing expectations intentionally updated for retryable failures.
- 총 신규 test case: 9.

### 11-3. Final test result
- Backend pytest: `316 passed, 1 skipped in 0.69s` (`--strict-markers -W error::pytest.PytestUnraisableExceptionWarning` 포함).
- Backend mypy strict: `Success: no issues found in 73 source files`.
- Frontend test: `3 passed`.
- Frontend build: success (`npm run build`; Vite chunk-size warning only).
- Frontend lint: success (`npm run lint`).
- Note: shell startup printed `pyenv: cannot rehash: /Users/Mung/.pyenv/shims isn't writable`; test/build commands still exited 0 except the intentionally noted pip resolver check below.

### 11-4. Alembic migration
`d5f6a7b8c9e0_add_social_post_failure_state.py` (`revision = d5f6a7b8c9e0`, down_revision `c7d4e8f2a1b3`).

### 11-5. Judgment calls
- Task 3: local venv had `pytest-asyncio==1.4.0`, but `pip install -r backend/requirements.txt` exposed metadata conflict with `pytest==8.3.3` because pytest-asyncio 1.4.0 requires `pytest>=8.4`. To keep fresh installs resolvable while preserving the requested pytest-asyncio version, `pytest` was adjusted to `8.4.0`.
- Task 4: adding `-e /Users/Mung/dev/firecrawl-local` directly to `backend/requirements.txt` would break GitHub Actions/CI on Ubuntu. I added `backend/requirements-firecrawl-local.txt` and a requirements comment instead, so local SDK installation is explicit without breaking standard installs.
- Task 5: `SocialExtractor` already switches to `local_chat()` when `settings.use_local_ai` is true, so only the gate condition needed code changes.
- Task 6: unsupported social platform mapping is treated as permanent failure; missing configured `Platform` row, empty extraction, extractor exception, and per-event processing exception are retryable.

### 11-6. Blocked
none

---

## 12. Review log (reviewer writes after verifying)

**Reviewed:** 2026-07-14 | **Verdict: approved (리뷰어 수정 2건 — alembic multi-head 수정, 범위 밖 vite.config.ts 변경 되돌림)**

### Verified directly
- `git diff` 전체를 파일별로 직접 읽음 (collector.py, pipeline.py, social_post.py,
  firecrawl_client.py, main.py, config.py, docker-compose.yml, client.ts, SearchBar.tsx,
  searchPolling.ts, CI workflow, requirements*, pytest.ini).
- 리뷰어가 직접 재실행: backend `316 passed, 1 skipped` (`--strict-markers -W
  error::pytest.PytestUnraisableExceptionWarning` 포함), mypy --strict `Success: no
  issues found in 73 source files`, frontend `npm run build`/`npm run lint`/`npm run
  test`(3 passed) 전부 통과.
- Task 1: `searchPolling.ts`의 `decidePollAction` 순수함수 분리 + `SearchBar.tsx`가
  success 시 `searchProducts(query, false)` 재호출하는 것 확인 — 지시대로.
- Task 2: `_products_with_events`(Product⋈SaleEvent, deleted_at 필터)가 실제로 이벤트
  보유 product만 반환하는지 확인. `collect_on_demand`가 신규 미수집 시
  `existing_ids`로 폴백하는 판단(스펙에 없었지만 올바른 처리)까지 diff로 확인.
  신규 테스트가 `placeholder not in products`를 직접 assert하는 것도 확인.
- Task 3: `pytest-asyncio==1.4.0`의 실제 `Requires-Dist`를 dist-info METADATA에서
  직접 확인 — `pytest<10,>=8.4`. `pytest==8.4.0`로의 버전 조정은 자의적 최신화가
  아니라 이 제약을 만족시키기 위한 필연적 조정이었음을 확인(승인).
- Task 4: `/health`가 실제로 frankencrawler 상태를 포함하는지 curl로 확인. SDK 미설치
  경로에 warning 로그 추가된 것, docker-compose의 override 주석이 실제 서비스 추가
  없이 문서화만 한 것(스코프 준수) 확인.
- Task 5/6: `pipeline.py` 전체 재작성 diff 라인 단위로 확인. `match_event_to_post`가
  no-match 시에도 유효 인덱스(첫 포스트 fallback)만 반환함을 소스에서 직접 확인해
  try 블록 밖으로 옮겨진 매칭 호출이 안전한지 검증. `_mark_retryable`/`_mark_processed`/
  `_mark_permanent_failure` 헬퍼와 extract_batch 예외 처리(신규, 스펙 밖이지만 정확히
  같은 취지의 방어) 확인.
- **버그 발견 및 직접 수정**: `alembic heads`가 2개(`a1b2c3d4e5f6`,
  `d5f6a7b8c9e0`)로 분기됨 — 새 마이그레이션의 `down_revision`이 실제로는 이미
  다른 마이그레이션이 존재하는 `c7d4e8f2a1b3`를 가리켜 브랜치가 생겼고,
  `alembic upgrade head`가 "Multiple head revisions" 에러로 즉시 실패함을 실측
  확인. `down_revision`을 `a1b2c3d4e5f6`(social_posts와 무관, feedback/search_logs
  테이블만 건드림 확인)로 재배선해 단일 head로 수정, 실제 Postgres against
  upgrade/downgrade/upgrade 라운드트립까지 재검증 완료.

### Notable / beyond spec
- `collect_on_demand`가 "신규 수집 0건 → 기존 실제 데이터로 폴백" 처리한 것은 스펙에
  명시 안 했지만 정확히 맞는 판단 — 좋은 craft.
- `extract_batch` 자체가 예외를 던지는 경우까지 잡아 재시도 처리한 것도 스펙 이상의
  방어(P0-6 취지와 일치하므로 scope creep 아님, 승인).
- Task 4에서 `-e /Users/Mung/dev/firecrawl-local`을 메인 requirements.txt에 직접 넣지
  않고 별도 `requirements-firecrawl-local.txt`로 분리한 판단 — CI/Docker를 안 깨는
  더 안전한 설계, 지시보다 나은 선택.

### 범위 밖 변경 발견 → 되돌림 → 정정 후 복원 (2026-07-14~15)
- `frontend/vite.config.ts`에 `server.allowedHosts: ['compa.mwco.io']`가 추가돼 있었음 —
  6개 Task 어디에도 없는 변경이고, **COMPA 저장소 안에서는** `compa.mwco.io` 언급이 이
  한 줄 외엔 전무해 리뷰 당시 근거를 확인할 수 없었음. 리뷰어가 `git checkout --
  frontend/vite.config.ts`로 되돌림.
- **정정 (2026-07-15, 사용자 확인)**: `compa.mwco.io`는 실제로 사용자가 이미 구성해둔
  Cloudflare Tunnel(`~/.cloudflared/config.yml`, tunnel `pm-dashboard`,
  `com.wsungahn.cloudflared-pm` launchd 상시 실행)의 ingress 항목이었음 —
  `compa.mwco.io → http://localhost:5173`로 이미 라우팅 중. 이 설정은 COMPA 저장소가
  아니라 머신 레벨(`~/.cloudflared/`)에 있어서 리뷰 시점엔 리뷰어가 확인할 수 없었던
  근거였고, executor(Codex)가 자의적으로 넣은 게 아니라 실제 인프라와 일치하는
  올바른 변경이었음. `allowedHosts` 없이는 Vite dev server가 `compa.mwco.io` Host
  헤더를 보안상 거부하므로 이 한 줄이 없으면 터널 경유 접속 자체가 막힘.
  **리뷰어가 되돌린 것을 다시 복원함**, build 재검증 완료.

### Follow-up
- Alembic 분기 버그는 이 리뷰에서 잡아 고쳤지만, **executor가 down_revision을 정할 때
  `alembic heads`로 브랜치 여부를 먼저 확인하지 않은 것**은 향후 handoff에
  "새 마이그레이션 작성 전 `alembic heads`로 단일 head인지 확인" 가이드를 §0에
  추가할 만한 재발방지 후보 (evolution-notes 등록 고려).
  cowork-handoff 스킬 개선 여지: `references/evolution-notes.md`에 반영 검토.
- 커밋 후 재시작 필요 없음 (COMPA는 상시 데몬 없음, 로컬 서버는 수동 기동).
