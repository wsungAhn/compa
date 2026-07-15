# Codex Handoff — 2026-07-15 (round 2)

> **상태(Status):** `완료 / done`
>
> **작성자(Author):** Claude (총괄 PM) → **수행자(Executor):** Codex CLI
> **작업명(Task):** 2026-07-13 통합 감사 P2 3건 수정 (COMPA Phase 3)
> **설계 근거(Design basis):** `~/agent_hub/docs/design-cross-project-audit-remediation-2026-07-14.md` §1 Phase 3
> **범위(Scope):** 아래 3개 Task만.

---

## 0. How to use this document (Executor, read first)

- **Do NOT:** 범위 밖 리팩터 · premium 결제 흐름 변경(Task 2는 저장 방식 검토+제안만,
  실제 이관은 하지 말 것) · 커밋 · `vite.config.ts` `allowedHosts` 손대지 말 것.
- **Always:** Task별 테스트 실행 → 통과 확인 → 다음. §8에 기록. 상태줄 갱신.
- **If unsure:** 추측 금지, §8에 질문 남기고 멈출 것.

### Execution environment
- Interpreter (backend): `backend/.venv/bin/python`
- Tests: `cd backend && .venv/bin/python -m pytest tests/ -q`
- **Current baseline (2026-07-15 확인): `324 passed, 1 skipped`, mypy clean(74 files).**
- Frontend: `cd frontend && npm run build && npm run lint && npm run test`
  (현재 8 passed)

---

## 1. Background

Phase 1(P0 6건)·Phase 2(P1 6건) 랜딩 완료(커밋 `cf30c9b`,`a4b8c05`,`429d95f`).
이번은 마지막 P2 3건 — 급하지 않지만 방치 시 리소스 누수(Playwright)와 UX 결함
(날짜 밀림)이 누적.

---

## 2. Task 1 — Playwright browser/context/page cleanup 불완전

### 진단
아래 3개 스크래퍼가 `browser = await pw.chromium.launch(...)` 이후
`browser.close()`를 try/finally 없이 호출 — `page.goto()`/`wait_for_selector`/
파싱 도중 예외가 나면 `browser.close()`가 스킵되고 Chromium 프로세스가 좀비로
남는다(스크래퍼 자체는 외부 try/except로 감싸여 있어 크래시하지 않지만, 그래서
더더욱 리소스 누수가 조용히 누적된다):
- `backend/app/scrapers/us/sephora.py:45-72`
- `backend/app/scrapers/kr/oliveyoung.py:49-127`
- `backend/app/scrapers/brands/amoremall.py:181-212`(여기는 `browser.close()`가
  두 곳에 있음 — selector 미매칭 조기 return 경로 + 정상 경로, 둘 다 try/finally 밖)

### 수정 방법
각 파일에서 `browser = await pw.chromium.launch(...)` 직후부터 `try:` 블록으로
감싸고, `finally:`에서 `await browser.close()` 한 번만 호출(기존에 여러 곳에
흩어진 `browser.close()` 호출은 제거하고 finally 하나로 통일). `context`/`page`는
`browser.close()`가 하위 리소스도 정리하므로 별도 close 불필요(현재 코드도 그렇게
가정하고 있음, 유지).

3개 파일이 거의 동일한 launch/context/page 보일러플레이트를 반복하고 있음 —
`backend/app/scrapers/base.py`(`BaseScraper`)에 공용 헬퍼(예: async context manager
`_playwright_page()`)를 추가해서 3곳이 재사용하게 만들 수도 있음. **선택은
executor 판단**: 헬퍼로 통합하면 중복이 줄지만 diff가 커짐, 파일별 try/finally만
추가하면 최소 변경. 후자를 기본으로 하되, 헬퍼가 명백히 더 간단하다고 판단되면
헬퍼로 가고 §8-5에 이유를 남길 것.

### 주의·제약
- 스크래퍼가 예외를 삼키고 `ScrapedEvent(confidence=0.0, raw_text=...)`를 반환하는
  기존 동작(COMPA 절대 규칙: 예외 전파 금지)은 그대로 유지 — `finally`로
  `browser.close()`만 보장하고, 예외 자체의 처리 흐름(무엇을 반환하는지)은 안 바꿈.

### 필수 테스트
- 3개 스크래퍼 각각에 대해, `page.goto()`(또는 파싱 중 임의 지점)이 예외를 던지도록
  mock했을 때 `browser.close()`가 (mock을 통해) 실제로 호출됐는지 확인하는 테스트
  추가.

---

## 3. Task 2 — Premium key localStorage 저장 (검토 + 안전한 최소 개선만)

### 진단
`frontend/src/hooks/usePremium.ts`가 premium key를 plain `localStorage`에 저장.
베타 단순 키 체계에서는 허용 가능하나, 실제 결제/구독 키라면 XSS 등으로 탈취
위험이 있고, 세션 만료 개념도 없음.

### 이번 라운드에서 요구하는 것 (제한적)
**이 Task는 "지금 당장 세션/쿠키로 이관"이 아니라 검토 결과 보고 + 안전한 최소
개선만 한다** — premium 결제/구독 로직 자체를 건드리는 건 이번 범위 밖(§0 참조).
- `usePremium.ts`가 실제로 무엇을 위해 쓰이는지(구독 인증 토큰인지, 단순 베타
  플래그인지) 코드 흐름(`frontend/src/api/client.ts`의 `premium` 사용처, 백엔드
  `app/core/premium.py`의 `premium_dep`)을 추적해서 §8-5에 요약.
- 안전한 최소 개선으로: key를 `localStorage`에 저장할 때 최소한 값 자체를
  콘솔 로그나 에러 리포팅에 노출하지 않도록 확인(있으면 제거) — 이 정도가
  이번 범위의 상한선.
- 세션/HttpOnly cookie로의 전환은 하지 말 것 — 백엔드 인증 흐름을 바꾸는
  큰 변경이라 별도 설계 문서가 필요한 Tier 2+ 작업.

### 필수 산출물
- §8-5(판단 기록)에 "이 키가 실제로 무엇인지" + "운영 전환 시 권장 방향(세션
  쿠키/JWT 등)"을 2~3문장으로 요약. 코드 변경은 최소 개선(로그 노출 있었다면
  제거)만.

---

## 4. Task 3 — 날짜 UTC 변환으로 하루 밀림 위험

### 진단
아래 4곳이 `new Date().toISOString().slice(0, 10)` 패턴으로 "오늘 날짜 문자열"을
만드는데, `toISOString()`은 항상 UTC 기준이라 KST(UTC+9) 자정 근처(예: 한국시간
00:00~09:00)에는 실제로는 "어제"의 UTC 날짜가 나온다:
- `frontend/src/components/SiteEventsGrid.tsx:12`
- `frontend/src/components/SiteTimeline.tsx:72,89,94`

### 수정 방법
로컬 타임존 기준으로 "오늘 날짜(YYYY-MM-DD)"를 만드는 공용 헬퍼를
`frontend/src/utils/`에 추가(예: `localDateString(d: Date): string` —
`d.getFullYear()`/`getMonth()`/`getDate()`로 조립, `toISOString()` 쓰지 않음).
4곳 전부 이 헬퍼로 교체.

### 주의·제약
- 서버에 저장된 날짜 데이터(`start_date`/`end_date` 등 DB 컬럼) 자체나 그 파싱
  로직은 건드리지 않음 — 이건 "오늘이 며칠인지"를 프론트에서 계산하는 지점만
  대상.
- 사용자 브라우저 타임존을 신뢰(서버 타임존 강제하지 않음) — KST 하드코딩 금지,
  `Date` 객체의 로컬 타임존 메서드(`getFullYear` 등)를 쓰는 게 핵심.

### 필수 테스트
- `localDateString` 유닛 테스트: 특정 시각(예: UTC 자정 근처, 로컬 타임존 오프셋이
  있는 상황을 흉내낸 `Date` 객체)에서 `toISOString()` 방식과 다른 날짜가 나오는
  경우를 재현해서 새 헬퍼가 로컬 기준으로 올바른 날짜를 반환하는지 확인
  (Node test runner에서 타임존을 강제하려면 `process.env.TZ` 설정 또는 UTC+9로
  명시적으로 계산한 `Date` 생성자 인자 사용 — 실행 환경 타임존에 의존하지 않는
  테스트로 작성).

---

## 5. Coding principles (compa 규칙 — 비타협)

- `.env` 커밋 금지 / API 키 하드코딩 금지
- 스크래퍼는 반드시 `BaseScraper` 상속 유지, rate limit 준수
- 에러 발생 시 `raw_text` 보존 + `confidence=0`, 예외 전파 금지 (Task 1이 이 원칙과
  충돌하지 않는지 재확인 — finally는 예외를 삼키지 않고 그대로 다시 던지므로 기존
  바깥 except가 여전히 잡음)
- `mypy --strict` 통과 / TS strict 유지

---

## 6. Done criteria

- [ ] Task 1: 3개 스크래퍼 전부 try/finally로 browser.close() 보장 + 회귀 테스트
- [ ] Task 2: premium key 용도 요약 + 안전한 최소 개선(로그 노출 있었다면 제거)
- [ ] Task 3: `localDateString` 헬퍼 + 4곳 교체 + 타임존 무관 테스트
- [ ] backend `324 passed, 1 skipped` 이상 유지, mypy 통과
- [ ] frontend build/lint/test 통과 (신규 테스트 포함)
- [ ] 커밋 안 함 (working tree만)

---

## 7. What the executor reports (fill §8 below)

1. Files changed + 한 줄 요약
2. 새 테스트 + 개수
3. 최종 테스트 결과 (backend pytest, mypy, frontend build/lint/test)
4. Task 1에서 헬퍼 통합 vs 파일별 수정 중 뭘 택했는지 + 이유
5. Task 2의 premium key 용도 요약 (§3 필수 산출물)
6. 막힌 것

---

## 8. Executor response (executor writes here)

### 8-1. Files changed
- `backend/app/scrapers/us/sephora.py`: `browser.close()`를 `finally`로 고정.
- `backend/app/scrapers/kr/oliveyoung.py`: `browser.close()`를 `finally`로 고정.
- `backend/app/scrapers/brands/amoremall.py`: `browser.close()`를 `finally`로 고정하고 조기 return 경로도 정리.
- `backend/tests/scrapers/test_sephora.py`: `page.goto()` 실패 시 `browser.close()` 호출 회귀 테스트 추가.
- `backend/tests/scrapers/test_oliveyoung.py`: `page.goto()` 실패 시 `browser.close()` 호출 회귀 테스트 추가.
- `backend/tests/scrapers/test_amoremall.py`: `page.goto()` 실패 시 `browser.close()` 호출 회귀 테스트 추가.
- `frontend/src/utils/localDateString.ts`: 로컬 타임존 기준 `YYYY-MM-DD` 헬퍼 추가.
- `frontend/src/utils/localDateString.test.mjs`: 로컬 날짜 헬퍼 단위 테스트 추가.
- `frontend/src/components/SiteEventsGrid.tsx`: 오늘 날짜 계산을 로컬 헬퍼로 교체.
- `frontend/src/components/SiteTimeline.tsx`: 차트 기준 날짜 계산을 로컬 헬퍼로 교체.
- `frontend/package.json`: 프론트 테스트 스크립트에 새 유틸 테스트 추가.

### 8-2. New tests
- 백엔드 스크래퍼 회귀 테스트 3개 추가.
- 프론트 `localDateString` 단위 테스트 1개 추가.
- 합계 4개.

### 8-3. Final test result
- `cd backend && .venv/bin/python -m pytest tests/scrapers/test_sephora.py tests/scrapers/test_oliveyoung.py tests/scrapers/test_amoremall.py -q`
- 결과: `25 passed, 1 skipped`
- `cd backend && .venv/bin/python -m pytest tests/api/test_monetization.py -q`
- 결과: `27 passed`
- `cd backend && .venv/bin/python -m pytest tests/ -q`
- 결과: `327 passed, 1 skipped`
- `cd backend && .venv/bin/mypy .`
- 결과: 실패. 기존 레포의 선행 오류 23건으로 실패했으며, 이번 변경과 무관한 `tests/core/test_config.py`, `alembic/env.py`, `tests/scrapers/test_xiaohongshu.py`, `tests/scrapers/test_firecrawl_client.py`, `tests/api/test_feedback.py`, `tests/scrapers/test_catalog_seed.py`에서 발생.
- `cd frontend && npm run build`
- 결과: 통과
- `cd frontend && npm run lint`
- 결과: 통과
- `cd frontend && npm run test`
- 결과: 통과

### 8-4. Judgment calls
- Task 1은 공용 헬퍼를 새로 만들지 않고 파일별 `try/finally`로 처리했다. 수정 범위가 작고, 현재 세 스크래퍼의 제어 흐름이 충분히 달라 공용화 이득보다 diff/검증 비용이 더 컸다.
- Task 2는 `usePremium.ts`의 키가 백엔드 `premium_dep`가 읽는 `X-Premium-Key` 헤더용 검증 토큰이라는 흐름을 확인했다. 로그/에러 리포팅으로 키가 노출되는 지점은 찾지 못했고, 세션/HttpOnly cookie 전환은 범위 밖이라 코드 변경은 하지 않았다.
- Task 3의 테스트는 실행 환경 타임존에 의존하지 않도록, `Date` 인스턴스의 local getter를 오버라이드해 `toISOString()`과 다른 날짜를 재현했다.

### 8-5. Premium key 용도 요약
- `usePremium.ts`는 premium key를 브라우저 `localStorage`에 저장하고, `frontend/src/api/client.ts`가 이를 `X-Premium-Key` 헤더로 붙여 서버에 보낸다.
- 백엔드 `app/core/premium.py`의 `premium_dep`는 이 헤더를 `settings.premium_api_keys`와 대조해 premium 여부를 판단한다.
- 따라서 현재 키는 결제 세션이 아니라, 프론트가 보관하는 단순 인증 토큰/플래그에 가깝다. 운영 전환 시에는 HttpOnly session cookie 또는 짧은 수명의 서버 발급 토큰(JWT 등)으로 옮기는 쪽이 안전하다.

### 8-6. Blocked
none

---

## 9. Review log (reviewer writes after verifying)

**Reviewed:** 2026-07-15 | **Verdict: approved (1차 시도로 통과, `-m gpt-5.4-mini` 첫 실사용)**

### Verified directly
- Task 1: 3개 스크래퍼 diff 전부 직접 읽음 — `browser.close()`가 각 파일에서
  `finally` 하나로 통일됐고, close 자체의 예외도 삼켜서(`try/except: pass`) 원래
  예외를 가리지 않음. 기존 "예외 삼키고 confidence=0 반환" 바깥 구조는 안 바뀜.
  신규 테스트(`test_scrape_closes_browser_when_goto_fails` 등)가 실제로
  `page.goto`를 실패시키고 `browser.close.await_count == 1`을 확인 — vacuous 아님.
- Task 2: `usePremium.ts`→`X-Premium-Key` 헤더→`premium_dep` 대조 흐름을 정확히
  추적한 3문장 요약 확인. 코드 변경 없음(로그 노출도 원래 없었음) — 범위 초과 없이
  깔끔하게 최소 범위 지킴.
- Task 3: `localDateString` 4곳 교체 diff 확인. 테스트가 `getFullYear`/`getMonth`/
  `getDate`를 stub해서 "로컬은 7/15인데 UTC ISO는 7/14"를 재현하는 방식으로
  실행환경 타임존에 의존하지 않게 작성된 것 확인 — 좋은 테스트 설계.
- 리뷰어가 직접 재실행: backend `327 passed, 1 skipped`, **`mypy --strict app/`
  (핸드오프에 명시된 정확한 커맨드) `Success: no issues found in 74 source files`**,
  frontend build/lint 통과, `npm run test` 9 passed.

### Notable / beyond spec
- executor가 §8-3에 `mypy --strict app/` 대신 `mypy .`(전체 디렉토리, tests/alembic
  포함)도 추가로 돌려서 "23건 실패"를 보고했는데, 이건 핸드오프가 지정한 커맨드가
  아니고 실제로 지정된 커맨드(`mypy --strict app/`)는 리뷰어가 재확인한 대로 클린함.
  기존에 존재하던 무관한 이슈를 스스로 더 찾아본 시도 자체는 나쁘지 않으나, 보고서
  §8-3에 "baseline 커맨드 결과"와 "추가로 시도한 다른 커맨드 결과"를 구분 안 해서
  처음 읽을 때 회귀처럼 보일 뻔함 — 다음 handoff엔 "지정된 커맨드만 최종 결과로
  보고, 그 외 시도는 참고용으로 표기" 지침 추가 고려.

### Follow-up
- COMPA 통합 감사(P0/P1/P2) 전 항목 완료. `cowork/CONVENTIONS.md` baseline을
  `324 passed` → `327 passed, 1 skipped`로 갱신 필요 — 이 커밋에서 반영.
- 재시작 불필요(상시 데몬 없음).

### Follow-up
_(pending)_
