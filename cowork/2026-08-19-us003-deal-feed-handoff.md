# Codex Handoff — 2026-08-19 · US-003 딜 신호 피드 구현

> **상태(Status):** `구현 완료 / implemented — DB·브라우저 검증은 로컬 sandbox 제약`
>
> **작성자(Author):** Claude Sonnet 5 (랩탑 D:\dev\compa) → **수행자(Executor):** Codex CLI
> **작업명(Task):** `/deals` placeholder를 실제 딜 신호 피드로 구현. 백엔드 신규
> 읽기 전용 API 1개 + 프론트 화면.
> **디자인 근거**: `designs/deal-feed/Deal-Feed.dc.html` — Claude Design 프로토타입.
> 데스크톱/모바일 populated 상태와 empty 상태 4개 프레임이 한 캔버스에 있다.
> **PRD 근거**: `docs/PRD-2026-08-07.md` §5 US-003, §6 FR-3.
> **선행 작업**: US-005(라우팅, `5cc7ecf`) 랜딩 완료 — `AdminMatchesPage.tsx`는
> 이미 구현됨(US-002, 참고용으로 패턴 재사용 가능 — `useAdminSecret` 말고
> `api/client.ts`의 axios 패턴, 로딩/에러 처리 스타일).
> **범위(Scope)**: in — `backend/app/api/deals.py`(신규, 읽기 전용 GET 1개),
> `backend/app/main.py`(라우터 등록 한 줄), `frontend/src/routes/DealFeedPage.tsx`,
> `frontend/src/api/client.ts`(함수 추가). out — `SocialPost`/`SaleEvent` 스키마
> 변경(FR-3 — 기존 스키마 유지, 새 읽기 전용 API만 추가), 다른 페이지.

---

## 0. How to use this document (Executor, read first)

- **하지 마라:** DB 스키마 변경(마이그레이션 없음) · `SocialPost` 저장 로직
  (`tasks/reddit_signals.py`) 수정 · 범위 밖 리팩터 · 커밋 · main 머지 · 서비스
  재시작 · `.env` 변경
- **항상:** 각 단계 후 빌드/린트/테스트 → 통과 확인. §4에 기록.
- **디자인과 실제 데이터의 차이(중요, 2절에 상세)**: 디자인 목업은 브랜드/제목/
  할인율/가격/서브레딧명이 전부 깔끔히 분리된 필드처럼 그리지만, 실제 저장
  구조(`SocialPost.content`)는 그 정보 일부를 **자유 텍스트 하나에 섞어서**
  담고 있다. 없는 필드를 지어내지 말고, 2절의 파싱 규칙을 정확히 따르며,
  파싱 실패/데이터 없음은 그 항목을 조용히 생략(빈 문자열 대신 UI에서 숨김)한다.

### Execution environment

- 백엔드 cwd: `backend/` · Interpreter: `/Users/Mung/dev/compa/backend/.venv/bin/python`
- 프론트 cwd: `frontend/` · Build: `npm run build` · Lint: `npm run lint` · Test: `npm run test`
- Type check: `mypy --strict app/` (백엔드 변경 시)
- **npm install 새 패키지 금지** — 기존 의존성으로 충분.
- DB 의존 검증(로컬 PG 연결)이 sandbox에서 막힐 수 있다 — 이전 라운드들에서
  실측된 패턴. 막히면 정직하게 기록하고 리뷰어가 재검증한다.

---

## 1. 배경

Reddit/Slickdeals에서 수집한 "지금 화제인 딜"은 이미 `social_posts` 테이블에
저장되지만, 그걸 읽는 API가 없다(저장만 되고 아무도 못 봄). 이 화면은 그
원본 신호를 사용자에게 최신순으로 보여준다. 48시간 지난 건 별도 배치
(`purge_expired_social_posts`)가 이미 지운다 — 이 API는 "지금 테이블에
있는 것"만 최신순으로 보여주면 된다(48시간 필터를 API에서 굳이 다시
안 걸어도 되지만, 걸어도 안전).

## 2. 실제 데이터 구조 및 파싱 규칙 (반드시 이대로)

`backend/app/models/social_post.py`의 `SocialPost` 컬럼: `id`, `platform`
(`"reddit"` | `"slickdeals"` 등 enum), `post_url`, `content`(자유 텍스트),
`posted_at`, `sale_event_id`(nullable — 아직 가격으로 승격 안 됐으면 null).

`content`는 `backend/app/tasks/reddit_signals.py`가 항상 이 형식으로 쓴다:
- Reddit: `"[{brand}] {title}"`
- Slickdeals: `"[{brand}] {title}"` 또는 가격이 있으면
  `"[{brand}] {title} (${price:,.2f})"` (예: `"[코스알엑스] 40% off (\$15.29)"`)

**API가 응답 생성 시 파싱할 것**(저장 로직은 건드리지 않고, 읽을 때만 파싱):
1. `brand`: `content`가 `^\[(?P<brand>[^\]]+)\]\s*(?P<rest>.+)$` 정규식에
   매치하면 `brand` 그룹 사용, 안 매치하면 `brand = None`(그리고 `rest`는
   원본 `content` 그대로).
2. `price`: `rest`의 끝이 `\s*\(\$(?P<price>[\d,.]+)\)\s*$` 패턴과 매치하면
   그 금액 문자열을 `price`로 쓰고 `rest`에서 그 부분을 제거해 `title`을
   만든다. 매치 안 하면 `price = None`, `title = rest` 그대로.
3. `discount_pct`: `backend/app/core/sale_windows.py`의 `parse_discount_pct(title)`
   함수를 그대로 재사용해 `title`에서 파싱 시도(이미 저장 시점에 쓰는 함수라
   재사용이 맞다 — 새로 만들지 마라). 실패하면 `None`.
4. `source`: `platform` 컬럼 그대로(`"reddit"` / `"slickdeals"`).
5. 서브레딧/스레드명(디자인의 "r/AsianBeauty" 같은 것): **저장 안 돼 있음,
   지어내지 마라.** 프론트에서 그 자리는 아예 표시 안 하거나 `source`만
   표시.

## 3. Task 목록

### T1 — 백엔드: 딜 신호 조회 API 신설

`backend/app/api/deals.py` 신규 파일:
```python
class DealSignalOut(BaseModel):
    id: uuid.UUID
    brand: str | None
    title: str
    discount_pct: float | None
    price: str | None
    source: str  # platform
    source_url: str | None
    posted_at: datetime | None

@router.get("/api/deals", response_model=list[DealSignalOut])
async def list_deal_signals(limit: int = 50) -> list[DealSignalOut]:
    ...
```
- 인증 없음(공개 API — 사용자용, `X-Admin-Secret` 불필요, FR-3 범위 내).
- `SocialPost`를 `posted_at desc`로 정렬해 최대 `limit`개 조회. `platform`이
  `"reddit"` 또는 `"slickdeals"`인 것만(다른 소셜 플랫폼은 이 API 범위 아님 —
  US-006 관련 데이터가 나중에 섞여도 여기 노출 안 되게).
- 2절 파싱 규칙을 정확히 적용해 `DealSignalOut`으로 변환.
- `main.py`에 라우터 등록(기존 라우터 include 패턴 그대로 따라 한 줄 추가).

### T2 — `api/client.ts`에 함수 추가

```ts
export interface DealSignal {
  id: string
  brand: string | null
  title: string
  discount_pct: number | null
  price: string | null
  source: string
  source_url: string | null
  posted_at: string | null
}
export async function listDeals(): Promise<DealSignal[]> { ... }  // GET /deals
```

### T3 — `DealFeedPage.tsx` 실제 구현

디자인(`designs/deal-feed/Deal-Feed.dc.html`)의 populated/empty 두 상태를
반응형으로(데스크톱 넓은 화면 = 디자인 desktop 프레임 레이아웃, 좁은 화면 =
mobile 프레임 레이아웃 — CSS 미디어쿼리 또는 조건부 렌더 중 프로젝트 관례에
맞는 쪽) 구현:
- 최신순 리스트, 각 행: 브랜드(있으면), 상대시간("N시간 전"/"N일 전" —
  `posted_at` 기준 클라이언트에서 계산), 제목, 소스 마커(작은 테두리 박스,
  디자인 스타일 그대로), 할인율(있으면, 포인트 컬러 `#0E96C1`, 없으면 그
  자리 생략), 가격(있으면, 없으면 생략), 원문 링크(`source_url`, 새 탭).
- **24시간 지난 항목은 옅게(opacity 0.72)** — 디자인의 `fadeStartHours: 24`
  기본값 그대로 하드코딩(설정 가능하게 만들 필요 없음).
- 빈 상태: "지금은 조용하네요" + 안내 문구(디자인 텍스트 그대로 가져와도 됨).
- 색상/폰트: US-002와 동일 시스템(`#0E96C1` 포인트, Space Grotesk+Instrument
  Sans — 이미 `index.html`에 폰트 로드돼 있음, US-002 커밋에서 추가됨).
- 로딩 상태 표시(실제 API 호출이 있으니 필요).

---

## 4. 완료 판정

- `mypy --strict` 0 errors, 기존 pytest 스위트 회귀 없음(DB 의존이라 sandbox
  제한 있으면 정직히 기록)
- `npm run build`/`lint`/`test` 통과
- `/deals` 접속 시 실제 `social_posts` 데이터가 최신순으로 표시
- 브랜드/할인율/가격 중 없는 필드는 UI에서 자연스럽게 생략(빈 칸이나 "N/A"
  아님)
- 24시간 지난 항목 옅게 표시
- 빈 대기열일 때 빈 상태 화면
- 회귀 없음: 다른 라우트에 영향 없음
- 커밋하지 않음 — 워킹트리 변경만

---

## 5. Executor Log (여기에 기록)

- 2026-08-19 Codex: 정본 핸드오프, 디자인 근거, PRD US-003/FR-3,
  `reddit_signals.py`, `sale_windows.py` 읽음. 제한사항 확인: 스키마 변경 없음,
  npm install 없음, 커밋 없음, 서비스 재시작 없음.
- 2026-08-19 Codex: 구현 진행. 신규 읽기 전용 `GET /api/deals` 추가,
  `SocialPost.content` 파싱은 문서 §2 규칙 그대로 적용, `parse_discount_pct()`
  재사용. 프론트 `/deals` placeholder를 실제 피드/empty/loading/error 상태로 교체.
- 2026-08-19 Codex: 검증 1차. `backend/.venv/bin/python -m pytest
  backend/tests/api/test_deals.py` 통과(2 passed). `backend/.venv/bin/python -m mypy
  --strict app/` 통과. `frontend npm run test` 통과(11 passed). `frontend npm run
  lint` 통과. `frontend npm run build` 통과(Vite chunk size warning만 출력).
  `backend/.venv/bin/python -m pytest` 전체는 486 passed / 8 skipped까지 진행 후
  로컬 PostgreSQL `::1:5432` 접속이 sandbox `PermissionError: [Errno 1] Operation
  not permitted`로 막혀 DB 의존 테스트가 실패함.
- 2026-08-19 Codex: 브라우저 검증 시도. 서비스 재시작 없이 임시 정적 서버를
  띄우려 했으나 localhost bind가 sandbox `PermissionError: [Errno 1] Operation
  not permitted`로 실패. Playwright 라우팅 방식도 시도했으나 번들 Chromium 미설치,
  시스템 Chrome headless 즉시 종료로 실패. 새 브라우저 다운로드/설치는 금지라 중단.
- 2026-08-19 Codex: 최종 재검증. `npm run lint`, `npm run test`, `npm run build`,
  `backend/.venv/bin/python -m pytest backend/tests/api/test_deals.py`,
  `backend/.venv/bin/python -m mypy --strict app/`, `git diff --check` 통과. 커밋하지 않음.

## 6. Reviewer Log (Claude Sonnet 5, 2026-08-19)

빌드/린트/테스트 직접 재검증(live PG): pytest 519 passed/1 skipped(+2 신규),
mypy 88 files 0 errors, npm build/lint/test(11 passed) 전부 통과.

`compa.mwco.io/deals` 실브라우저 확인 중 1건 발견·수정: API 서비스가 재시작
전이라 `/api/deals`가 (신규 라우터를 못 읽어서) 404 → SPA fallback이 그걸
삼켜 `index.html`을 200으로 반환 → 프론트가 `.map()` 호출 시 크래시(빈 화면).
`launchctl kickstart`로 API 재시작 후 정상 확인 — 실제 데이터가 디자인
그대로(브랜드/상대시간/소스뱃지/가격) 렌더링됨.

**별도 발견(이번 작업 범위 밖, 후속 확인 필요)**: 화면에 "4일 전" 딜이 보임 —
Reddit 약관상 48시간 보존 강제 대상인데 위반. `purge_expired_social_posts`
배치가 최근 정상 실행됐는지 별도 확인 필요(서비스가 8/9~8/18 정지 상태였던
이력과 관련 있을 수 있음). 이 작업 코드와는 무관 — 후속 이슈로 트래킹.

커밋 승인.
