# Codex Handoff — 2026-07-15

> **상태(Status):** `완료 / done`
> _(Executor: set `진행중 / in-progress` on start, `검토대기 / review-pending` when done.
>  Only the author/reviewer sets `완료 / done`, after the commit.)_
>
> **작성자(Author):** Claude (총괄 PM) → **수행자(Executor):** Codex CLI
> **작업명(Task):** 2026-07-13 통합 감사 P1 6건 수정 (COMPA Phase 2)
> **설계 근거(Design basis):** `~/agent_hub/docs/design-cross-project-audit-remediation-2026-07-14.md` §1 Phase 2
> **범위(Scope):** 아래 6개 Task만. Phase 3(P2: Playwright cleanup, premium key 저장방식, UTC 날짜)는 범위 밖.

---

## 0. How to use this document (Executor, read first)

- **Do NOT:** 범위 밖 리팩터 · premium/결제 코드 변경 · DB 스키마 직접 변경(Alembic 필수) ·
  커밋 (working tree만 남길 것) · `frontend/vite.config.ts`의 `allowedHosts` 설정
  건드리지 말 것(머신 레벨 Cloudflare Tunnel과 짝을 이루는 설정, 무관해 보여도 손대지 않음).
- **Always:** 각 Task 끝날 때마다 테스트 실행 → 통과 확인 → 다음 Task. §8에 기록.
  시작/종료 시 상단 상태줄 갱신.
- **If unsure:** 추측 금지. §8에 질문으로 남기고 멈출 것.

### Execution environment
- Interpreter (backend): `backend/.venv/bin/python`
- Tests: `cd backend && .venv/bin/python -m pytest tests/ -q`
- Type check: `cd backend && .venv/bin/python -m mypy --strict app/`
- Frontend: `cd frontend && npm run build && npm run lint && npm run test`
- **Current baseline (2026-07-15 확인): backend `316 passed, 1 skipped`, mypy clean,
  frontend build/lint/test(3 passed) 전부 통과.** 이 아래로 떨어지면 회귀.

---

## 1. Background

Phase 1(P0 6건)은 이미 랜딩됨(커밋 `cf30c9b`, `a4b8c05`). 이번은 같은 2026-07-13
감사의 P1 6건 — 성능/보안/UX 개선. 사용자 대면 긴급도는 P0보다 낮지만 방치하면
데이터 정합성(중복 product)과 보안(secret 노출)에 영향.

---

## 2. Task 1 — Product matcher가 매 호출마다 전체 products 테이블 로드 (P1)

### 진단
`backend/app/ai/matcher.py:76-88` (함수는 `find_matching_product` 내부):
```python
result = await db.execute(
    select(Product).where(
        Product.deleted_at.is_(None),
    )
)
candidates = list(result.scalars().all())
```
country별 매칭 대상 하나 찾으려고 삭제 안 된 전체 Product를 매번 메모리로 끌어온 뒤
Python에서 `normalize_name()` 비교. 제품 수가 늘어날수록 매 collect 호출마다 선형
비용이 붙는다.

### 수정 방법
Stage 1(정확 일치)을 SQL로 좁힌다 — country별 컬럼(`name_kr`/`name_en`/`name_jp`/`name_cn`)에
`func.lower(column) == func.lower(:name)` 조건을 WHERE에 넣어 DB가 후보를 좁히게 한다.
정규화(`normalize_name`)가 SQL로 표현 안 되는 부분(공백/특수문자 처리 등)이 있으면,
"brand 일치 + 대략적인 ILIKE 좁히기"로 1차 후보군을 줄인 다음 그 좁혀진 후보들에서만
Python `normalize_name` 정밀 비교를 적용 — 즉 "전체 테이블 로드"를 "brand/유사도로
좁힌 후보 N개 로드"로 바꾸는 게 핵심이지, 완벽한 SQL 정규화가 목표가 아니다.
`Product`에 이미 pg_trgm(`docs/AUDIT-2026-06-10.md` 언급, 실제 인덱스는 마이그레이션
확인)이 있으면 `similarity()`로 후보를 좁히는 것도 고려.

### 주의·제약
- 매칭 정확도(현재 통과하는 테스트들의 기대 결과)를 유지할 것 — 성능 개선이 매칭
  로직 자체를 바꿔서 다른 제품이 매칭되면 안 됨.
- Stage 2(brand match)/Stage 3 이후 로직 구조는 유지, Stage 1의 후보 조회 방식만 변경.

### 필수 테스트
- 기존 매칭 테스트가 전부 통과하는지 확인(회귀 없음).
- 대량 product(예: 100개 이상 mock/fixture)에서 실행되는 쿼리 수가 줄었는지 확인하는
  테스트(SQL 쿼리 카운트 또는 후보 리스트 크기 assert) 추가.

---

## 3. Task 2 — Product 중복 생성 race condition (P1)

### 진단
`backend/app/ai/matcher.py:184-229`(`get_or_create_product`)이 "찾고 없으면 생성" 패턴인데
DB에 unique constraint가 없다(`backend/app/models/product.py`에 `UniqueConstraint`/
`unique=True` 전무, 2026-07-15 확인). 병렬 collector/worker가 동시에 같은 제품을
못 찾고 각자 생성하면 중복 Product가 생긴다.

### 수정 방법
`(country별 name 컬럼, brand)` 조합 또는 서비스 특성에 맞는 조합에 partial unique
index를 Alembic 마이그레이션으로 추가. `get_or_create_product`는 생성 시
`IntegrityError`(unique violation)를 잡아서 재조회 후 반환하는 upsert-safe 패턴으로
수정(예: `try: insert → except IntegrityError: await db.rollback(); return await
find_matching_product(...)`).

### 주의·제약
- DB 스키마 변경은 Alembic 필수 — `alembic heads`로 단일 head인지 먼저 확인 후
  `down_revision` 설정(2026-07-14 리뷰에서 멀티헤드 버그가 실제로 배포를 막은 전례 있음).
- 기존 데이터에 이미 중복이 있을 수 있음 — unique index 추가가 실패하면(중복 존재)
  마이그레이션에서 실패 원인을 로그로 남기고 §8에 보고, 강제로 데이터 삭제하지 말 것.

### 필수 테스트
- 동시 요청(`asyncio.gather`로 같은 이름 두 번 `get_or_create_product` 호출) 시
  Product가 1개만 생성되는지 확인하는 테스트.

---

## 4. Task 3 — Admin feedback secret이 query string으로 전달 (P1)

### 진단
`backend/app/api/feedback.py:53-56`:
```python
@router.get("/api/admin/feedback", response_model=list[FeedbackOut])
async def get_admin_feedback(secret: str) -> list[FeedbackOut]:
```
GET + query param이라 `secret`이 URL에 그대로 남아 브라우저 히스토리/프록시
로그/access 로그에 노출되기 쉽다.

### 수정 방법
`secret`을 쿼리 파라미터 대신 `X-Admin-Secret` 헤더로 받도록 변경
(`Header(...)` 의존성 또는 `Request.headers`). 비교는 이미 있는
`_is_authorized_feedback_secret`을 유지하되 내부 비교를 `hmac.compare_digest()`로
바꿔 타이밍 공격 표면을 줄인다.

### 주의·제약
- 프론트엔드에 이 admin 엔드포인트를 호출하는 코드가 있으면 헤더 방식으로 함께 수정
  (`frontend/src/`에서 `/api/admin/feedback` 검색해서 호출부 확인).
- 엔드포인트 경로 자체(`/api/admin/feedback`)는 바꾸지 않음.

### 필수 테스트
- 헤더 없이 호출 시 404(또는 401), 올바른 헤더로 호출 시 200 확인하는 테스트로 기존
  query-param 테스트를 교체.

---

## 5. Task 4 — source_url/post_url 검증 부족 (P1)

### 진단
아래 지점들이 스크래퍼/AI/소셜에서 온 URL을 검증 없이 저장·href로 사용:
- `backend/app/scrapers/collector.py:205` (`source_url=s.source_url`)
- `backend/app/ai/pipeline.py:216` (`source_url=matched_post.post_url`)
- `backend/app/api/products.py:310`, `backend/app/api/comparison.py:115` (`to_affiliate_url(e.source_url, ...)`)
- `frontend/src/components/SiteTimeline.tsx:146,179` (`currentUrl`을 그대로 `href`에 사용)

### 수정 방법
Backend에 공용 `safe_url(url: str | None) -> str | None` 헬퍼를 추가(예:
`app/core/` 아래)해서 `http://`/`https://` 스킴만 허용, 그 외(`javascript:`, `data:`
등)는 `None`으로 치환. 저장 시점(`collector.py`, `pipeline.py`)과 응답 시점
(`products.py`, `comparison.py`)의 `to_affiliate_url` 호출부 앞뒤 중 저장 시점에
한 번 적용하는 걸 우선(중복 검증 방지). 가능하면 플랫폼별 host allowlist까지
고려하되, 최소 스킴 검증은 필수.

Frontend `SiteTimeline.tsx`에도 동일한 `safeUrl` 헬퍼(TS) 추가해서 `href`에 넣기
전에 스킴 검증 — backend가 이미 걸러도 프론트 방어벽을 이중으로 둔다.

### 주의·제약
- 기존 정상 URL(https 스킴)이 걸러지면 안 됨 — 화이트리스트가 아니라 스킴
  검증(+선택적 host allowlist) 수준으로 최소 침습적으로.

### 필수 테스트
- `javascript:alert(1)`, `data:text/html,...` 같은 악성 스킴이 `None`/차단되는지,
  정상 `https://` URL은 그대로 통과하는지 확인하는 단위 테스트(backend `safe_url`,
  frontend `safeUrl` 각각).

---

## 6. Task 5 — Frontend 검색 debounce 없음 (P1)

### 진단
`frontend/src/components/SearchBar.tsx`의 `handleSearch(q)` (43-58행 부근)가 매
키 입력마다 `searchProducts(q, false)`를 즉시 호출 — debounce 없음.
`docs/known-issues.md` 또는 관련 문서에 "300ms debounce"라고 적혀 있다면 실제
코드와 불일치.

### 수정 방법
`handleSearch` 호출부(입력 change handler)에 300ms debounce 추가 — 이미
`searchPolling.ts`처럼 별도 유틸(`debounce.ts` 또는 유사)로 순수 함수 분리하는
패턴을 따를 것(Task 1의 순수함수 분리 전례 참고). 오래된 응답이 새 응답을 덮어쓰지
않도록 AbortController 또는 요청 순번(sequence id)으로 stale response 방지도 함께.

### 주의·제약
- Enter 키로 즉시 검색(`handleKeyDown`)하는 기존 동작은 유지 — debounce는 타이핑
  중 자동완성/미리보기 검색에만 적용.

### 필수 테스트
- debounce 유틸에 대한 단위 테스트(연속 호출 시 마지막 호출만 실행되는지, 타이머
  기반이므로 `vi.useFakeTimers()` 또는 Node test runner의 시간 제어 활용).

---

## 7. Task 6 — npm audit high 2건 (P1)

### 진단
```
form-data  4.0.0 - 4.0.5   (high, CRLF injection)
vite       8.0.0 - 8.0.15  (high, launch-editor NTLMv2 hash disclosure / server.fs.deny bypass)
@babel/core <=7.29.0        (low)
```
전부 `npm audit fix`로 해결 가능(2026-07-15 확인).

### 수정 방법
`cd frontend && npm audit fix` 실행. `vite` 메이저 버전이 올라가면(8.0.15→8.0.16+
이내인지 확인) `npm run build`/`npm run lint`/`npm run test`가 전부 여전히
통과하는지 검증. CI(`.github/workflows/ci.yml`)에 `npm audit --audit-level=high`
스텝 추가해서 향후 회귀를 CI가 잡게 한다.

### 주의·제약
- `npm audit fix --force`(breaking change 포함)는 쓰지 말 것 — 먼저 `npm audit
  fix`만 시도하고, 그래도 안 잡히는 게 있으면 §8에 보고.

### 필수 테스트
- `npm run build && npm run lint && npm run test` 전부 통과, `npm audit`에서 high
  0건 확인.

---

## 8. Coding principles (compa 규칙 — 비타협)

- `.env` 커밋 금지 / API 키 하드코딩 금지
- `requests` 금지 → `httpx.AsyncClient`
- DB 스키마 변경은 Alembic 필수, **적용 전 `alembic heads`로 단일 head 확인**
- `mypy --strict` 통과 / TS strict 유지 / 테스트 없는 변경 금지

---

## 9. Done criteria

- [ ] Task 1: matcher 전체테이블 로드 → 좁혀진 후보 조회
- [ ] Task 2: product unique constraint + race condition 안전 처리
- [ ] Task 3: admin feedback secret 헤더 방식 전환
- [ ] Task 4: source_url/post_url 스킴 검증 (backend+frontend)
- [ ] Task 5: 검색 debounce 300ms
- [ ] Task 6: npm audit high 0건
- [ ] backend `316 passed, 1 skipped` 이상 유지, mypy 통과, frontend build/lint/test 통과
- [ ] 커밋 안 함 (working tree만)

---

## 10. What the executor reports (fill §11 below)

1. Files changed + 한 줄 요약
2. 새 테스트 + 개수
3. 최종 테스트 결과 (backend pytest, mypy, frontend build/lint/test, npm audit)
4. Alembic migration 생성했으면 revision id + `alembic heads` 출력
5. 판단이 필요했던 부분
6. 막힌 것

---

## 11. Executor response (executor writes here)

### 11-1. Files changed
- `.github/workflows/ci.yml` — frontend CI에 `npm audit --audit-level=high` 추가.
- `backend/app/ai/matcher.py` — Product match 후보 조회를 exact/brand 제한 쿼리로 변경, unique violation 후 rollback/re-query 처리.
- `backend/alembic/versions/e6a7b8c9d0f1_add_product_country_name_brand_unique_indexes.py` — country별 name + normalized brand active partial unique index 추가.
- `backend/app/api/feedback.py` — admin secret을 `X-Admin-Secret` 헤더로 전환, `hmac.compare_digest()` 사용.
- `backend/app/core/url_safety.py` — `http`/`https`만 허용하는 `safe_url()` 추가.
- `backend/app/scrapers/collector.py`, `backend/app/ai/pipeline.py` — 저장 시 source/post URL scheme 검증.
- `backend/app/api/products.py`, `backend/app/api/comparison.py` — 응답/affiliate 변환 전 URL scheme 재검증.
- `frontend/src/utils/urlSafety.ts`, `frontend/src/components/SiteTimeline.tsx` — frontend href 직전 URL scheme 검증.
- `frontend/src/utils/debounce.ts`, `frontend/src/components/SearchBar.tsx` — 검색 입력 300ms debounce + sequence 기반 stale response 방지.
- `frontend/package.json` — frontend unit test 대상 추가.
- `backend/tests/ai/test_matcher.py`, `backend/tests/api/test_feedback.py`, `backend/tests/core/test_url_safety.py`, `frontend/src/utils/urlSafety.test.mjs`, `frontend/src/utils/debounce.test.mjs` — 회귀 테스트 추가/보강.

### 11-2. New tests
- Backend 8개 추가: matcher 후보 제한/unique violation 재조회/brand 없는 dirty-name normalize fallback 3개, admin feedback header 2개, URL safety 3개.
- Frontend 5개 추가: `safeUrl` 3개, `debounce` 2개.
- 최종 테스트 수: backend `324 passed, 1 skipped`, frontend node tests `8 pass`.

### 11-3. Final test result
- `cd backend && .venv/bin/python -m pytest tests/ -q` → `324 passed, 1 skipped in 2.71s`
- `cd backend && .venv/bin/python -m mypy --strict app/` → `Success: no issues found in 74 source files`
- `cd frontend && npm run build && npm run lint && npm run test` → build 통과, lint 통과, `8 pass`
- `cd frontend && npm audit fix` → 실패: `getaddrinfo ENOTFOUND registry.npmjs.org`
- `cd frontend && npm audit --audit-level=high` → 실패: `getaddrinfo ENOTFOUND registry.npmjs.org`

### 11-4. Alembic migration
- Revision: `e6a7b8c9d0f1`
- `alembic heads` 출력: `e6a7b8c9d0f1 (head)`
- index: `uq_products_name_kr_brand_active`, `uq_products_name_en_brand_active`, `uq_products_name_jp_brand_active`, `uq_products_name_cn_brand_active`

### 11-5. Judgment calls
- Product unique index는 country별 name 컬럼과 `lower(coalesce(brand, ''))` 조합으로 잡았다. `brand IS NULL` 중복도 막아야 race condition 완화가 유효하기 때문.
- unique index는 `deleted_at IS NULL` + 해당 name 컬럼 `IS NOT NULL` partial index로 제한했다. soft-deleted row와 다른 country name이 비어 있는 row를 막지 않기 위함.
- admin feedback header 누락은 FastAPI validation 422 대신 기존 은닉 동작과 맞춰 404로 처리했다.
- URL 검증은 저장 시점뿐 아니라 API 응답 시점에도 적용했다. 기존 DB에 남아 있을 수 있는 악성 URL 방어 목적.
- `npm audit fix`가 DNS 차단으로 실패했고 package integrity를 확인할 수 없어 lockfile/package version을 임의 수정하지 않았다. 불완전하게 생긴 `package-lock.json` side effect는 원복했다.

### 11-6. Blocked
- `npm audit fix` 및 `npm audit --audit-level=high`가 네트워크 DNS 차단으로 registry에 접근하지 못해 실패: `getaddrinfo ENOTFOUND registry.npmjs.org`. 따라서 Task 6의 “npm audit high 0건”은 이 환경에서 검증/완료 불가.

---

## 12. Review log (reviewer writes after verifying)

**Reviewed:** 2026-07-15 | **Verdict: approved (전체 6개 Task, Task 1은 재수정 라운드 후 승인)**

### Verified directly
- Task 2(unique index): `alembic heads` 단일head 확인, 실제 Postgres에 upgrade/
  downgrade/upgrade 라운드트립 검증 완료. 마이그레이션이 기존 중복 데이터를 먼저
  체크(`RAISE EXCEPTION`)하는 것도 확인 — 안전.
- Task 3(feedback secret): 헤더 방식 전환 + `hmac.compare_digest` 확인.
- Task 4(URL 검증): `safe_url`/`safeUrl` 스킴 검증 로직과 4개 적용 지점(collector,
  pipeline, products, comparison, SiteTimeline) 전부 확인. 테스트 통과.
- Task 5(debounce): `SearchBar.tsx`의 sequence 기반 stale-response 방지까지 정확히
  구현됨 확인.
- Task 6(npm audit): executor가 codex 샌드박스 네트워크 차단(`getaddrinfo ENOTFOUND
  registry.npmjs.org`)으로 `npm audit fix` 실패를 정직하게 §11-6에 보고함(좋은
  판단 — 억지로 우회하거나 거짓 성공 보고하지 않음). **리뷰어가 네트워크 있는
  환경에서 직접 `npm audit fix` 실행 — `found 0 vulnerabilities`**, build/lint/test
  재검증 완료(vite 8.0.15→상위 버전, 8 tests pass).
- 리뷰어가 전체 재실행: backend `323 passed, 1 skipped`, mypy clean, frontend
  build/lint/test(8 pass) 전부 확인.

### 🔴 Task 1 — 회귀 버그 발견 → 수정 완료 (2026-07-15 재검증)
**재검증 결과: 승인.** executor가 brand 있음/없음 두 경로 모두에 정밀
`normalize_name()` 재비교를 추가(brand 없으면 전체 후보를 로드해 Python
비교하는 fallback, brand 있으면 브랜드로 좁힌 후보에서 먼저 정밀 매치 시도 후
count==1 휴리스틱). **리뷰어가 원래 repro 스크립트로 직접 재실행 — 이제
정확히 매치됨**(`no-brand result: e45a6a10... expected: e45a6a10...`, 일치).
신규 회귀 테스트(`test_exact_match_fallback_normalizes_dirty_name_without_brand`)도
같은 케이스를 고정. 전체 재실행: backend `324 passed, 1 skipped`, mypy clean.

<details><summary>원래 발견 경위 (참고용, 해결됨)</summary>


`find_matching_product`의 Stage 1이 `func.lower(country_column) == normalized_input`로
SQL에서 직접 비교하도록 바뀌었는데, `normalize_name()`은 HTML 태그 제거 +
공백 collapse까지 하는 반면 SQL `lower()`는 대소문자만 처리한다. `get_or_create_product`가
저장 시 **원본 `name`을 그대로** 저장하므로(정규화 안 함), DB에 공백/HTML이 섞인
이름이 있으면 Stage 1 SQL 비교가 정규화된 쿼리와 절대 일치하지 않는다.

**리뷰어가 실제 Postgres DB로 직접 재현**:
```python
# brand 없이(Stage 2 구제 불가능하게) 검증
dirty_name = "  <b>설화수</b>   윤조에센스  "
p = Product(name_kr=dirty_name, brand=None)
# ... db.add(p); await db.flush()
result = await find_matching_product(db, "설화수 윤조에센스", None, "KR")
# result == None  (기대값: p.id) — Stage 1이 못 찾음, 이전 코드는 찾았을 것
```
brand가 있는 케이스(기존 테스트들 전부 brand 지정)에서는 Stage 2가 우연히 구제해서
버그가 가려짐 — 이번 라운드의 신규 테스트도 전부 brand가 있거나 이미 정규화된
깨끗한 이름만 써서 이 회귀를 못 잡았다.

**영향**: 스크래핑된 이름에 공백/HTML 변형이 실제로 존재할 수 있음(이 프로젝트
자체가 스크래퍼 기반) — brand 없는 product나 우연히 다른 brand로 매칭 안 되는
경우, 같은 제품이 재수집될 때마다 중복 Product가 생길 수 있다. Task 2의 unique
index는 `lower(name, brand)`만 비교하므로 이 특정 케이스(공백/HTML 차이)를
막지도 못한다 — 두 버그가 상호작용해서 사각지대를 만듦.

**요청하는 수정**: Stage 1을 "SQL로 안전하게 좁힌 후보 → Python normalize_name
정밀 비교"의 2단계로 다시 설계할 것. 예:
1. SQL은 완전 일치 대신 좁히기만 담당 — 예를 들어 brand가 있으면 brand로 먼저
   좁히고(이미 Stage 2가 하고 있음), brand가 없으면 정규화 입력값의 앞 N글자로
   `ILIKE` prefix 매칭 등으로 후보를 줄인 다음, 그 후보들에 대해서만 Python
   `normalize_name(col_value) == normalized_input` 정밀 비교.
2. 또는 더 단순하게: SQL 정확매치가 0건이면 즉시 실패로 끝내지 말고, 전체
   테이블에서 (deleted_at IS NULL AND 해당 컬럼 IS NOT NULL)만 필터링한 후보로
   Python normalize_name 비교하는 fallback 경로를 추가(예전 방식 그대로) —
   이러면 "이미 SQL로 찾아지는 깨끗한 데이터"는 빠른 경로를 타고, "더러운 데이터"만
   느린 fallback을 타므로 대부분의 실질 성능 이득은 유지된다.

어느 방향이든 **§8 방식대로 실행 전 리뷰어가 준 위 repro 스크립트로 먼저
재현하고, 수정 후 같은 스크립트로 해소됐는지 직접 확인할 것**. 그리고 brand 없는
케이스를 위 repro처럼 테스트로 고정해서 §11-2에 추가.

</details>

### Notable / beyond spec
- Task 2의 `IntegrityError` catch + rollback + re-query 패턴, 동시성 테스트
  (`test_concurrent_create_recovers_from_unique_violation`)가 실제
  `asyncio.gather`로 두 개의 독립된 mock db session을 동시에 실행해 검증한 것 —
  스펙 이상의 견고한 테스트.
- Task 6에서 npm audit 실패를 숨기지 않고 정직하게 blocked로 보고한 것 — 이번
  세션 전체에서 가장 좋은 executor 판단 중 하나.

### Follow-up
_(pending)_
