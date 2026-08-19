# Codex Handoff — 2026-08-19 · US-004 매칭 커버리지 대시보드 구현

> **상태(Status):** `구현 완료 / done — 전체 mypy는 기존 테스트 타입 부채로 실패`
>
> **작성자(Author):** Claude Sonnet 5 (랩탑 D:\dev\compa) → **수행자(Executor):** Codex CLI
> **작업명(Task):** `/admin/coverage` placeholder를 실제 매칭 커버리지 화면으로
> 구현. 백엔드 신규 읽기 전용 API 1개 + 프론트 화면.
> **디자인 근거**: `designs/matching-coverage/Matching-Coverage.dc.html`.
> **PRD 근거**: `docs/PRD-2026-08-07.md` §5 US-004, §6 FR-4.
> **범위(Scope)**: in — `backend/app/api/admin.py`에 커버리지 엔드포인트 1개
> 추가(FR-4 — "새 집계 테이블 만들지 않는다"는 요건은 지키되, 이 화면 전용
> API 신설 자체는 US-004 acceptance criteria가 요구하는 것), `main.py` 라우터
> 등록(이미 admin 라우터는 등록돼 있으면 불필요), `frontend/src/routes/CoveragePage.tsx`,
> `api/client.ts` 함수 추가. out — 새 집계 테이블/컬럼 신설(FR-4 — 기존
> `products`/`product_match_candidates` 테이블 단순 카운트 쿼리로 충분).

---

## 0. How to use this document (Executor, read first)

- **하지 마라:** 새 테이블/컬럼 마이그레이션(FR-4 금지) · 범위 밖 리팩터 ·
  커밋 · main 머지 · 서비스 재시작 · `.env` 변경
- **항상:** 각 단계 후 빌드/린트/테스트 → 통과 확인. §4에 기록.
- **디자인과 실제 데이터의 차이(중요, 2절에 상세)**: 이번 건 데이터 필드가
  없는 게 아니라 **디자인이 가정한 시스템 범위 자체가 실제보다 넓다.** 정확히
  2절대로 스코프를 좁혀서 구현하고, 없는 걸 있는 것처럼 보이게 하지 마라
  (특히 "지난 배치 신규 매칭" 숫자와 "KR-JP-US" 문구).

### Execution environment

- 백엔드 cwd: `backend/` · 프론트 cwd: `frontend/`
- Build/Lint/Test: US-002/003 핸드오프와 동일 명령
- **npm install 새 패키지 금지.** DB 의존 검증이 sandbox에서 막히면 정직히
  기록 — 리뷰어가 재검증한다.

---

## 1. 배경

운영자가 "전체 카탈로그 중 크로스 통화 매칭이 얼마나 끝났는지"를 한눈에 보는
화면. 배치 주기(6시간, `celery beat`의 `match-products-6h`,
`backend/app/tasks/__init__.py` 참고)가 충분한지 판단하는 용도다.

## 2. 디자인 목업 vs 실제 시스템 범위 — 반드시 이대로 스코프 조정

### 2-1. "orphan(미매칭)"의 실제 정의를 그대로 재사용할 것

`backend/app/tasks/match_products.py`의 `_match_pending_products`가 이미
"미매칭"을 정의하는 쿼리를 갖고 있다 — **새로 정의하지 말고 그 조건을 그대로
재사용**:
```python
Product.name_en.is_(None),
Product.name_jp.isnot(None),
Product.deleted_at.is_(None),
Product.brand.isnot(None),
```
이게 이 시스템에서 "미매칭 orphan"의 유일한 기존 정의다.

### 2-2. 디자인의 "KR–JP–US" 문구는 실제 범위보다 넓다 — 문구 수정 필요

디자인 상단 라벨이 "교차 매칭 커버리지 · KR–JP–US"라고 돼 있는데, 실제로
지금 시스템이 라이브 검증된 크로스 매칭은 **JP→EN(US) 한 방향뿐**이다
(`docs/PRD-2026-08-07.md` §7 Non-Goals: "한국·중국 소스의 완전한 크로스
통화 매칭(JP만 라이브 검증됨)"). 2-1의 orphan 정의도 `name_jp`가 있고
`name_en`이 없는 경우만 잡는다 — 즉 orphan 샘플의 "소스 국가" 컬럼은
현재 시스템 범위상 **거의 항상 JP로 나올 것이다**(다른 나라 데이터가
이 필터에 안 걸리니까). 이건 버그가 아니라 시스템이 실제로 그렇게 스코프돼
있는 것 — 그대로 보여줘라.

**문구 수정**: 상단 라벨을 "교차 매칭 커버리지 · KR–JP–US" 대신 실제
스코프에 맞게 "교차 매칭 커버리지 (JP → EN 백필)" 같은 정확한 문구로
바꿔라. 정확한 워딩은 구현자 재량이되, 실제보다 넓은 범위를 주장하지 마라.

### 2-3. "지난 배치에서 신규 매칭" — 이 숫자는 만들 수 없다, 빼라

디자인은 `newlyMatched: +316` 같은 배치 간 델타를 보여주는데, 이 값을 계산하려면
"이전 배치 시점의 카운트"를 어딘가 저장해둬야 하는데 **그런 이력 테이블이
없다.** FR-4는 "새 집계 테이블을 만들지 않는다"고 명시하므로, 이 델타를 위해
새 테이블을 만드는 것도 범위 밖이다. **이 지표는 화면에서 뺀다.** (총
카운트/매칭 카운트/orphan 카운트/커버리지 %는 전부 그 순간의 단순 카운트
쿼리라 문제없이 그대로 구현.)

### 2-4. "마지막 배치 / 다음 배치 시각"은 계산 가능 — 그대로 구현

`celery beat`의 `match-products-6h` 스케줄은 `crontab(minute=40, hour="*/6")`
(`backend/app/tasks/__init__.py`)다 — 즉 00:40/06:40/12:40/18:40 UTC마다
돈다. 프론트에서 현재 시각 기준으로 "마지막 배치"/"다음 배치" 시각을
계산해 표시해도 된다(서버가 정확히 그 시각에 실행됐다는 보장은 없지만
스케줄 자체는 사실이다 — 코멘트로 "스케줄 기준"임을 명시하면 됨). 굳이
구현이 부담되면 이 부분만 빼고 "배치 주기 6시간"만 표시해도 무방 —
판단은 구현자 재량.

## 3. Task 목록

### T1 — 백엔드: 커버리지 API 신설

`backend/app/api/admin.py`에 추가(같은 파일 — 기존 어드민 API들과 같이
관리, `X-Admin-Secret` 인증 재사용):
```python
class CoverageOrphanOut(BaseModel):
    brand: str | None
    name: str | None  # name_jp
    source_country: str  # 사실상 항상 "JP" — 2-2 참고
    unmatched_days: int  # now - created_at, 일수

class CoverageOut(BaseModel):
    total_count: int
    matched_count: int
    orphan_count: int
    coverage_pct: float
    orphans: list[CoverageOrphanOut]  # 샘플, 최대 8개

@router.get("/api/admin/coverage", response_model=CoverageOut)
async def get_coverage(
    x_admin_secret: Optional[str] = Header(default=None, alias="X-Admin-Secret"),
) -> CoverageOut:
    ...
```
- `total_count`: `Product.deleted_at.is_(None)` 전체 카운트.
- orphan 조건: 2-1 그대로.
- `matched_count = total_count - orphan_count`.
- orphan 샘플: 위 조건에 맞는 Product 중 최대 8개(정렬 기준은 구현자
  재량 — `created_at asc`로 오래된 것부터 보여주면 "7일 이상"이 잘
  드러나서 자연스러움).
- `unmatched_days`: `(now - Product.created_at).days` — orphan이 "언제부터"
  미매칭이었는지 직접 기록된 컬럼이 없어서 `created_at`을 근사치로 쓴다
  (완벽하진 않지만 지어낸 값은 아니다 — 실제 생성 시점 기준).

### T2 — `api/client.ts`에 함수 추가

`getCoverage(): Promise<Coverage>` — GET `/admin/coverage`, `X-Admin-Secret`
헤더 필요(US-002에서 만든 `useAdminSecret`/`setAdminSecretHeader` 재사용 —
이 페이지도 관리자 전용이라 같은 인증 흐름 공유).

### T3 — `CoveragePage.tsx` 실제 구현

- 시크릿 게이트: US-002의 `AdminMatchesPage`와 동일 패턴 재사용(코드
  중복보다 일관성 우선 — 컴포넌트 추출은 자유, 안 해도 됨).
- 포컬 메트릭: 큰 숫자(coverage %) + `matched/total` 텍스트, orphan 수,
  커버리지 바(디자인의 얇은 바 그대로). "신규 매칭" 숫자는 2-3에 따라
  뺀다.
- 하단 orphan 샘플 표: 브랜드/상품명/소스국가/미매칭기간 4컬럼, 7일
  이상은 진하게(디자인의 `days >= 7` 기준 그대로).
- 색상/폰트: US-002/003과 동일 시스템(`#0E96C1`, Space Grotesk+Instrument
  Sans — 이미 로드돼 있음).
- "전체 orphan 내보내기" 링크(디자인에 있음): 실제 내보내기 기능은 범위
  밖 — 링크는 비활성 처리하거나 안 만들어도 됨(디자인 장식 요소, 없는
  기능을 있는 척 만들지 마라).

---

## 4. 완료 판정

- `mypy --strict` 0 errors, 기존 pytest 회귀 없음
- `npm run build`/`lint`/`test` 통과
- `/admin/coverage` 접속(시크릿 입력 후) 시 실제 카운트 표시
- 문구가 실제 시스템 범위(JP→EN 백필)를 정확히 반영(2-2)
- "신규 매칭" 델타 없음(2-3)
- 커밋하지 않음 — 워킹트리 변경만

---

## 5. Executor Log (여기에 기록)

- 2026-08-19 Codex: 실행 시작. 핸드오프/디자인/PRD/`_match_pending_products`
  orphan 조건/현재 워킹트리 상태를 확인함. 스코프는 JP→EN 백필 커버리지,
  배치 델타 제거, 새 테이블/패키지/커밋/서비스 재시작 없음으로 고정.
- 2026-08-19 Codex: `backend/app/tasks/match_products.py`의 orphan predicate
  4개를 `orphan_product_filters()`로 추출하고, 기존 배치 쿼리의
  `ProductMatchCandidate.id.is_(None)` 중복 방지 조건은 유지함.
- 2026-08-19 Codex: `GET /api/admin/coverage` 추가. active product count,
  shared orphan count, `matched = total - orphan`, coverage %, 오래된 orphan
  샘플 최대 8건을 반환. 샘플 source_country는 실제 범위대로 `JP`.
- 2026-08-19 Codex: `/admin/coverage` placeholder를 실제 화면으로 교체.
  `useAdminSecret`/`setAdminSecretHeader` 재사용, 라벨은
  `교차 매칭 커버리지 (JP -> EN 백필)`, 지난 배치 신규매칭 델타와
  전체 orphan export 링크는 제거.
- 2026-08-19 Codex: 검증 결과:
  `.venv/bin/mypy --strict app/api/admin.py app/tasks/match_products.py` 통과,
  `.venv/bin/pytest tests/api/test_admin.py` 10 passed,
  `.venv/bin/pytest` 521 passed / 1 skipped,
  `npm run test` 13 passed,
  `npm run build` 통과(Vite chunk size warning만 표시),
  `npm run lint` 통과,
  `git diff --check` 통과.
- 2026-08-19 Codex: 전체 `backend/.venv/bin/mypy --strict .`는 기존 테스트/알렘빅
  타입 annotation 및 기존 `type: ignore` 문제 141건으로 실패. 변경 앱 파일
  기준 mypy는 통과했고, 신규 coverage 테스트 함수에는 annotation을 추가해
  `tests/api/test_admin.py`의 기존 오류 수를 늘리지 않음.
- 2026-08-19 Codex: 브라우저 스크린샷 검증은 미실행. Browser/Playwright 도구가
  현재 세션에 없고 Playwright 패키지도 설치돼 있지 않아, `npm install` 금지
  규칙을 지키기 위해 추가 설치하지 않음. 서비스 재시작/커밋도 하지 않음.

## 6. Reviewer Log (Claude Sonnet 5, 2026-08-19)

`mypy --strict app/`(프로젝트 정식 검증 범위)는 0 errors — Codex가 보고한
141건은 `tests/`/`alembic/`까지 포함한 전체 스캔이라 컨벤션 밖, 기존부터
있던 무관한 부채. 실제 검증:

- `mypy --strict app/`: 0 errors (88 files).
- `pytest tests/ -q` (live PG): 521 passed, 1 skipped (+2 신규, 회귀 0).
- `npm run build`/`lint`/`test`(13 passed) 전부 통과.
- API 서비스 재시작 후 `compa.mwco.io/admin/coverage` 실브라우저 확인 —
  "마지막 배치 18:40 UTC · 다음 배치 00:40 UTC · 스케줄 기준" 정확히 표시
  (celery beat crontab(minute=40, hour="*/6")과 일치), 시크릿 게이트 UI
  일관된 스타일.
- `orphan_product_filters()`로 `_match_pending_products`의 조건을 함수로
  추출해 admin.py 커버리지 API와 공유 — 정의 중복 없이 재사용됨(지시대로).

커밋 승인.
