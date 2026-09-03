# Codex Handoff — 2026-09-02

> **상태(Status):** `완료 / done`
>
> **시작 기록(Started by):** `session=CDEC0162-92D0-4221-92FA-7A1DF02FA7EF machine=mac started=2026-09-03T07:40:28Z`
>
> **작성자(Author):** Claude (Sonnet 5, Mac Studio) → **수행자(Executor):** Codex CLI
> **작업명(Task):** compa의 Ollama 배선 2지점(분석 chat, 번역 chat)에 llama.cpp 백엔드 스위치 추가 — 병행 운영, 기본값은 그대로 `ollama`
> **설계 근거(Design basis):** `~/agent_hub/docs/design-ollama-to-llamacpp-migration-addendum-compa-aibroker-2026-09-02.md` §A (승인/APPROVED, Round 2·3 2연속 CLEAN) — **읽어라, 이 핸드오프는 그 §A 요약이 아니라 실행 계획이다.**
> **위험 등급:** compa에 매매·금전 실행 경로 없음. A-2(분석 chat)는 위험도 하(현재 트래픽 0), A-3(번역)은 하~중(상시 데몬이 6시간마다 호출).
> **범위(Scope):** `backend/app/ai/local_client.py`, `backend/app/ai/translator.py`, `backend/app/core/config.py`, `backend/.env.example`. **범위 밖:** `.env` 자체(커밋 금지), `firecrawl_extract_provider` 경로(§2.4가 소유), premium/결제 코드, DB 스키마.

---

## 0. How to use this document (Executor, read first)

- **Do NOT:** `backend/.env` 수정/커밋(`.env.example`만), `USE_LOCAL_AI`를 임의로 켜서 검증(§6 참고 — 사용자 확인 필요), premium/결제 코드 건드리기, DB 스키마 직접 변경(Alembic 필수 영역이나 이번 스코프엔 스키마 변경 없음), 커밋(리뷰어가 함).
- **Always:** 각 태스크 후 `mypy --strict app/` + `pytest tests/ -q` 실행 → 통과 확인 → 다음. §8에 기록. 시작 시 이 문서 상단 "시작 기록"에 스탬프.
- **불확실하면:** 추측하지 말고 §8-6에 남겨라.

### Execution environment
- Interpreter: `backend/.venv/bin/python` (Python 3.11.8)
- Test: `cd backend && .venv/bin/python -m pytest tests/ -q`
- Type check: `cd backend && .venv/bin/python -m mypy --strict app/`
- **Current baseline (2026-08-08 CONVENTIONS.md 기준, 착수 전 재실측 필수):** `484 passed, 1 skipped`(로컬 PostgreSQL 가동 중 기준). 그 1 skipped(`tests/scrapers/test_amoremall.py:160`)는 상시 스킵 — 건드리지 마라.
- 워크트리에는 `.venv`가 없다 — main의 venv를 쓰되 cwd는 워크트리로: `PYTHONPATH=. /Users/Mung/dev/compa/backend/.venv/bin/python -m pytest tests/ -q`
- **상시 데몬 3개**(`com.compa.api/worker/beat`)가 `WorkingDirectory=/Users/Mung/dev/compa/backend`(= main 체크아웃)에서 돈다. 워크트리에서 고쳐도 운영은 구코드를 계속 돈다 — 재시작은 리뷰어가 머지 후 수행.

---

## 1. Background

`backend/app/ai/local_client.py`(분석 chat)와 `backend/app/ai/translator.py`(ja/zh→en 번역)가 각각 독립적으로 Ollama를 호출한다. 이번 작업은 각각에 llama.cpp(OpenAI 호환 `/v1/chat/completions`) 백엔드 옵션을 추가하는 것 — 기존 Ollama 경로는 그대로 두고 config 스위치로 병행한다(7일 상한 원칙, 모문서 §1).

**중요한 비대칭:** `local_client.py`(A-2)는 **이미 OpenAI 호환**(`{ollama_url}/v1/chat/completions`)이라 URL·모델 분기만 추가하면 끝 — body/응답파싱 코드는 한 줄도 안 바꾼다. `translator.py`(A-3)는 **Ollama 네이티브 `/api/generate`**를 쓰므로 이게 유일한 실질 전환 작업이다.

**추가로 확인된 사실 (착수 전 알아둘 것):** 지금 `backend/.env`(라이브 정본) 기준 `USE_LOCAL_AI`가 꺼져있어서 A-2 분석 chat 경로는 **현재 프로덕션에서 매시간 호출되지만 LLM에 안 닿고 0을 반환**한다(죽어있는 경로). A-3 번역 경로는 `use_local_ai`를 안 보고 6시간마다 진짜로 호출되므로 **살아있다.**

---

## 2. Task 1 — `local_client.py` (A-2, 최소 diff) — P1

### 진단
`config.py:27-33`: `ollama_url`(기본 `http://localhost:11434`, 오리진-온리), `local_ai_model`. `local_client.py:35`가 `f"{settings.ollama_url}/v1/chat/completions"`로 이미 OpenAI 호환 호출 중. body(`:36-41`: model/messages/temperature=0.1/stream=false)와 응답 파싱(`:50-54`: `result["choices"][0]["message"]["content"]`)은 llama-server가 내는 것과 그대로 일치.

### 수정 방법
`config.py`에 신규 필드 2개 추가:
```python
local_ai_backend: str = "ollama"      # "ollama" | "llamacpp"
llamacpp_url: str = "http://127.0.0.1:8082"   # 오리진-온리, /v1 넣지 말 것
llamacpp_ai_model: str = ""           # O-A1 종속, 기본값 미정 — 빈 문자열 유지
```
`local_client.py:35` 근방에서 `local_ai_backend`에 따라 base URL과 모델을 분기(`ollama_url`+`local_ai_model` vs `llamacpp_url`+`llamacpp_ai_model`). **body 구성(`:36-41`)과 응답 파싱(`:50-54`)과 예외 처리(`:56-69`)는 절대 바꾸지 마라** — 이미 두 백엔드 다 만족한다.

### 주의·제약
- `local_ai_backend`는 `use_local_ai`(로컬 vs Claude)와 **직교** — 하나로 합치지 마라(3상태를 2상태 bool에 욱여넣게 됨).
- QF-1(실패 시 빈 문자열 반환, `:44-69` 전 예외 경로)은 **그대로 유지** — 없애지 마라. 이건 CLAUDE.md의 "예외 전파 금지" 규칙이 만든 의도된 설계다.

### 필수 테스트
`local_ai_backend="llamacpp"`일 때 올바른 URL/모델로 요청이 가는지 mock으로 확인하는 테스트 1-2개 추가. 기존 `tests/ai/test_pipeline.py:229,251,282,332,380`의 `mock_settings.use_local_ai` True/False 5케이스는 **그대로 통과해야 한다**(기존 축 무변경 증명).

---

## 3. Task 2 — `translator.py` (A-3, 유일한 실질 전환) — P1

### 진단
`config.py:31-33`: `translation_ollama_url`(기본 `http://localhost:11434`, 오리진-온리), `local_translation_model`(`translategemma:4b`). `translator.py:38-70`(`_call_translategemma`)이 `f"{settings.translation_ollama_url}/api/generate"`(Ollama 네이티브)로 **동기** `httpx.post` 호출. body `{"model","prompt","stream":false}`(`:44-48`), 응답 `result.get("response","")`(`:59`). `match_products.py:103`이 `asyncio.to_thread(translate_for_matching, ...)`로 감싸므로 **동기 시그니처 유지 필수**.

### 수정 방법
`config.py`에 신규 필드 3개:
```python
translation_backend: str = "ollama"   # "ollama" | "llamacpp", local_ai_backend와 독립
translation_llamacpp_url: str = "http://127.0.0.1:8083"   # 오리진-온리, O-A2 결론 종속(임시값)
llamacpp_translation_model: str = ""  # O-A1 종속
```
`_call_translategemma`에 `translation_backend`별 분기:
| 항목 | Ollama(현행) | llama.cpp(신규) |
|---|---|---|
| 엔드포인트 | `{base}/api/generate` | `{base}/v1/chat/completions` |
| body | `{"model","prompt","stream":false}` | `{"model","messages":[{"role":"user","content":<같은 프롬프트>}],"stream":false}` |
| 응답 | `result.get("response","")` | `result["choices"][0]["message"]["content"]` |
| 시그니처 | 동기 | **동기 유지** |
| 실패 계약 | 비200/HTTPError/ValueError → `None` | **동일하게 `None`** |

### 주의·제약
- **`_build_translate_prompt`(`:22-35`)는 절대 건드리지 마라** — 실측된 프롬프트다. `/v1/chat/completions`로 옮길 때 system/user로 쪼개고 싶은 유혹이 있는데, **쪼개지 말고 통째로 user 메시지 하나에 그대로 넣어라.**
- `_looks_like_translation_failure`(`:73-84`), `detect_language`, 인메모리 캐시(`:14-15,143-145`), `canonicalize_brand_mentions`(`:157`)는 구조·값 그대로 보존.
- QF-2(번역 실패 시 원문 반환)·QF-3(매칭에서 None→skip) 폴백 경로도 유지.

### 필수 테스트
llama.cpp 분기의 body/응답파싱을 mock으로 검증하는 테스트 1-2개. 동기 시그니처가 유지됐는지(즉 `async def`로 안 바뀌었는지) 확인.

---

## 4. `backend/.env.example` 갱신
신규 env 6개 문서화: `LOCAL_AI_BACKEND`, `LLAMACPP_URL`, `LLAMACPP_AI_MODEL`, `TRANSLATION_BACKEND`, `TRANSLATION_LLAMACPP_URL`, `LLAMACPP_TRANSLATION_MODEL`. 접두사(`COMPA_`) 붙이지 않는다 — compa 기존 env 6개가 전부 무접두사라 짝 이름 일관성이 우선.

## 5. Coding principles
`CLAUDE.md`: `.env` 커밋 금지, `requests` 금지(httpx.AsyncClient만, 단 A-3은 기존처럼 동기 httpx), async 라우트 내 동기 호출 금지(A-3은 원래 동기라 예외), `mypy --strict` 통과 필수, 에러 시 `raw_text` 보존 + `confidence=0` + 예외 전파 금지.

## 6. Done criteria
- [ ] Task 1: `local_client.py` llama.cpp 분기, body/응답파싱 무변경 확인
- [ ] Task 2: `translator.py` llama.cpp 분기, 동기 시그니처 유지 확인
- [ ] `backend/.env.example` 갱신
- [ ] 신규 테스트 통과 + `tests/ai/test_pipeline.py`의 기존 5케이스 무회귀
- [ ] `mypy --strict app/` 통과
- [ ] `pytest tests/ -q` 무회귀(baseline 재실측 대비)
- [ ] **실 llama-server 상대 검증(§6 참고, 리뷰어가 직접 하거나 executor가 시도)**: A-2는 `USE_LOCAL_AI=true`가 필요해 **프로덕션 설정 변경**이므로 executor가 임의로 켜지 말 것 — mock 테스트까지만 하고 §8-6에 "실 서버 스모크는 리뷰어 확인 필요"로 남겨라.
- [ ] §8-7 자기채점
- [ ] 커밋 안 함

**이 핸드오프 범위 밖(리뷰어가 별도로 수행):**
- 실 llama-server 상대 A-2 20건 fixture 검증(`USE_LOCAL_AI=true`, 별도 프로세스 격리 env)
- 실 llama-server 상대 A-3 ja10+zh10 fixture 왕복 검증, Ollama 대비 1:1 대조표
- 상시 데몬 3개 무영향 확인(`launchctl print gui/$(id -u)/com.compa.{api,worker,beat}` — `launchctl list | grep`은 오탐 가능하니 보조로만)

### Acceptance rubric
| Dimension | What 5 means | Gate |
|---|---|---|
| Correctness | A-2/A-3 body·응답파싱 정확, `_build_translate_prompt` 무변경 | 5 (게이트) |
| Regression safety | 기본값 `ollama` 무변경, 기존 QF-1/2/3 폴백 경로 보존, 기존 5케이스 무회귀 | 5 (게이트) |
| Contract fidelity | A-3 동기 시그니처 유지(`asyncio.to_thread` 호출부 안 깨짐) | 5 (게이트) |

## 7. Executor response (executor writes here)
### 7-1. 착수 전 확인
- 시작 기록 반영: `session=CDEC0162-92D0-4221-92FA-7A1DF02FA7EF machine=mac started=2026-09-03T07:40:28Z`
- 범위 확인: `backend/app/core/config.py`, `backend/app/ai/local_client.py`, `backend/app/ai/translator.py`, `backend/.env.example`
- 설명서/설계 확인: 본 문서 §0, 설계 부록 §A

### 7-2. baseline
- `PYTHONPATH=. /Users/Mung/dev/compa/backend/.venv/bin/python -m mypy --strict app/` → `Success: no issues found in 88 source files`
- `PYTHONPATH=. /Users/Mung/dev/compa/backend/.venv/bin/python -m pytest tests/ai/test_local_client.py tests/ai/test_translator.py tests/ai/test_pipeline.py -q` → `47 passed`
- `PYTHONPATH=. /Users/Mung/dev/compa/backend/.venv/bin/python -m pytest tests/ -q` → 환경 의존 실패

### 7-3. 구현 기록
- `Settings`에 `local_ai_backend`, `llamacpp_url`, `llamacpp_ai_model`, `translation_backend`, `translation_llamacpp_url`, `llamacpp_translation_model` 추가
- `local_chat()`은 `local_ai_backend`에 따라 `ollama` / `llamacpp` base URL과 model을 분기하도록 수정
- `_call_translategemma()`는 `translation_backend`에 따라 `Ollama /api/generate`와 `llama.cpp /v1/chat/completions`를 분기하도록 수정
- `llama.cpp` 응답은 `choices[0].message.content`로 파싱하고, 키/인덱스 오류도 `None`으로 흡수
- `backend/.env.example`에 신규 env 6개를 문서화
- `backend/tests/ai/test_local_client.py`를 추가하고 `backend/tests/ai/test_translator.py`에 llama.cpp 분기 검증과 sync 시그니처 검증을 추가

### 7-4. 검증
- 통과: `mypy --strict app/`
- 통과: `tests/ai/test_local_client.py`
- 통과: `tests/ai/test_translator.py`
- 통과: `tests/ai/test_pipeline.py`
- 실패: 전체 `pytest tests/ -q`는 기존 DB 연결/권한 문제로 실패

### 7-5. 변경 파일
- [`backend/app/core/config.py`](/Users/Mung/dev/compa/backend/app/core/config.py)
- [`backend/app/ai/local_client.py`](/Users/Mung/dev/compa/backend/app/ai/local_client.py)
- [`backend/app/ai/translator.py`](/Users/Mung/dev/compa/backend/app/ai/translator.py)
- [`backend/.env.example`](/Users/Mung/dev/compa/backend/.env.example)
- [`backend/tests/ai/test_local_client.py`](/Users/Mung/dev/compa/backend/tests/ai/test_local_client.py)
- [`backend/tests/ai/test_translator.py`](/Users/Mung/dev/compa/backend/tests/ai/test_translator.py)

### 7-6. 미해결·주의사항
- 전체 `pytest tests/ -q`는 `PermissionError: [Errno 1] Operation not permitted`와 PostgreSQL 연결 실패로 깨졌다.
- 실패 지점은 `tests/api/test_admin.py`, `tests/tasks/test_match_products.py`, `tests/tasks/test_sale_windows.py` 등 DB 의존 테스트에 집중되어 있었고, 이번 변경 파일의 회귀는 `47 passed`로 통과했다.
- `USE_LOCAL_AI=true` 실서버 스모크는 요청대로 수행하지 않았다.

### 7-7. 자기채점
- Correctness: 5/5
- Regression safety: 4/5
- Contract fidelity: 5/5
- 총평: 구현 범위 내 요구사항은 충족했지만, 전체 테스트는 현재 로컬 환경 제약으로 끝까지 통과 확인하지 못했다.

## 8. Review log
**Reviewed:** 2026-09-02 (Claude/Sonnet, mac-studio) | **Verdict:** 승인 (커밋함)

- `local_client.py`/`translator.py`/`config.py` diff 전체 line-by-line 확인 — 스펙대로 base_url/model 분기, body/응답파싱 무변경(A-2), A-3의 엔드포인트/body/응답shape 전환 정확(`/api/generate`→`/v1/chat/completions`, `result.get("response","")`→`choices[0].message.content`), **동기 시그니처 유지 확인**(`inspect.iscoroutinefunction` 테스트로 직접 고정돼 있음). `_build_translate_prompt` 무변경 확인. 예외 처리에 `KeyError`/`IndexError`/`TypeError` 추가한 건 새 응답 shape 파싱 실패 대비로 타당한 확장.
- 신규 테스트 4개(`test_local_client.py` 2개, `test_translator.py` llama.cpp shape 1개 + 동기 시그니처 고정 1개) 내용 직접 읽음 — mock으로 실제 URL/body/응답 검증, 트리비얼 아님.
- 독립 실행(내 실환경, executor의 sandbox와 다름): `mypy --strict app/` → `Success, no issues found`. `pytest tests/ai/test_local_client.py tests/ai/test_translator.py tests/ai/test_pipeline.py -q` → `47 passed`(executor 보고와 일치, `test_pipeline.py`의 기존 5케이스 포함 무회귀). **전체 스위트**: `pytest tests/ -q` → **`527 passed, 1 skipped`** — executor가 보고한 sandbox 실패(`20 failed, 28 errors`, PermissionError + PostgreSQL 연결 불가)는 내 환경(로컬 PostgreSQL 가동 중)에서 전혀 재현 안 됨, 순수 sandbox 환경 아티팩트로 확인.
- `.env.example` 갱신 확인(`backend/.env`는 미변경 — 커밋 대상에서 올바르게 제외됨).
- Rubric 재채점: Correctness 5/5, Regression safety 5/5(기본값 `ollama` 무변경, QF-1/2/3 보존, 527 passed), Contract fidelity 5/5(동기 시그니처 테스트로 직접 고정) — executor 자기채점과 일치.
- 실 llama-server 스모크(A-2/A-3 fixture 검증)는 이 리뷰에서 미수행 — `USE_LOCAL_AI=true`가 프로덕션 설정 변경이라 사용자 확인 필요, 별도로 진행.
- 커밋: 이 리뷰 직후 5개 변경 파일 + 신규 테스트 파일 + 이 handoff 문서를 하나의 커밋으로 landing. 상시 데몬 재시작은 하지 않음(기본값이 `ollama`라 이번 커밋만으로는 동작 변화 없음 — 재시작 불필요).
