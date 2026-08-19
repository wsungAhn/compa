# Codex Handoff — 2026-08-19 · US-005 프론트엔드 라우팅 도입

> **상태(Status):** `대기 / pending`
>
> **작성자(Author):** Claude Sonnet 5 (랩탑 D:\dev\compa) → **수행자(Executor):** Codex CLI
> **작업명(Task):** react-router 도입, 기존 검색/비교 화면을 그대로 홈 라우트로 감싸고
> 딜피드(US-003)·매칭 검토(US-002)·매칭 커버리지(US-004)용 자리(placeholder route)만
> 미리 만들어 둔다. 이 3개 화면 자체의 UI 구현은 이 작업 범위 밖 — 디자인 브리프가
> 별도로 나온 뒤 후속 핸드오프로 진행된다.
> **PRD 근거**: `docs/PRD-2026-08-07.md` §5 US-005, §6 FR-5.
> **범위(Scope)**: in — `frontend/package.json`(react-router 의존성 추가),
> `frontend/src/main.tsx`(Router 설정), `frontend/src/App.tsx`(라우트 분리 — 기존
> 로직/마크업은 그대로 두고 라우트 컨테이너로만 감싼다), 신규 빈 페이지 컴포넌트
> 3개(아래 참고). out — US-002/003/004의 실제 화면 UI, 백엔드 API 신설.

---

## 0. How to use this document (Executor, read first)

- **하지 마라:** 기존 컴포넌트(`SearchBar`, `PriceComparison`, `WaitBuyWidget` 등)
  재작성 · 범위 밖 리팩터 · 커밋 · main 머지 · 서비스 재시작 · `.env` 변경
- **항상:** 각 Task 후 테스트/빌드 실행 → 통과 확인. §3에 기록.
- **핵심 원칙(FR-5)**: 기존 검색→비교 플로우가 **회귀 없이** 동작해야 한다 —
  라우팅 도입 자체가 목적이지, 화면을 새로 만드는 게 아니다.

### Execution environment

- cwd: `frontend/` · Node/npm 기존 환경 그대로 사용
- Build: `npm run build`
- Lint: `npm run lint`
- Test: `npm run test` (있는 경우)
- 프론트는 `npm run build`만 하면 API 재시작 없이 즉시 반영된다(`frontend/dist`를
  FastAPI가 직접 서빙 — `ops/README.md` 참고). **단, 이 작업은 워킹트리에만
  남기고 build/배포는 리뷰어가 검증 후 진행한다.**

---

## 1. Task 목록

### T1 — react-router 설치 및 Router 설정

1. `npm install react-router-dom` (React 19 호환 최신 버전 — v7 계열).
2. `frontend/src/main.tsx`에 `BrowserRouter`(또는 v7 방식이면 `createBrowserRouter`
   + `RouterProvider`, 프로젝트 관례에 맞는 쪽 선택)로 최상위를 감싼다.

### T2 — 기존 App을 홈 라우트로 분리

`App.tsx`의 현재 내용(검색바, WaitBuyWidget, PriceComparison, SiteEventsGrid,
EventTimeline, PriceChart, SiteManager, AdSlot, FeedbackButton, PremiumBanner 전부
포함한 지금 그대로의 화면)을 **그대로** `/` 경로의 컴포넌트로 이동한다. 로직·상태
관리(useState, useEffect, fetchProductData 등)는 한 글자도 안 바꾼다 — 파일
위치와 라우트 등록만 바뀌는 것.

권장 구조(강제 아님, 프로젝트 관례에 맞게 판단):
```
frontend/src/
  routes/
    HomePage.tsx          # 기존 App.tsx 내용 그대로 이동
    AdminMatchesPage.tsx   # 신규, 빈 placeholder
    DealFeedPage.tsx       # 신규, 빈 placeholder
    CoveragePage.tsx       # 신규, 빈 placeholder
  App.tsx                  # 라우트 정의만 (Routes/Route 또는 router config)
```

### T3 — Placeholder 페이지 3개

각각 최소한의 내용만(빈 화면 + 페이지 제목 정도):

- `/admin/matches` → `AdminMatchesPage` — "매칭 검토 화면 (준비 중)" 정도의
  텍스트만. US-002 구현 시 이 파일을 채운다.
- `/deals` → `DealFeedPage` — "딜 피드 (준비 중)". US-003 구현 시 채운다.
- `/admin/coverage` → `CoveragePage` — "매칭 커버리지 (준비 중)". US-004 구현 시
  채운다.

이 페이지들에 실제 기능을 넣지 마라 — 이번 작업은 라우팅 뼈대만 만드는 것.

### T4 — 회귀 확인

- `/` 경로에서 기존 검색→비교 플로우가 라우팅 도입 전과 **동일하게** 동작하는지
  `npm run build` + 로컬 미리보기로 확인(가능하면 `dev-browser` 스킬로 브라우저
  검증 — PRD Acceptance Criteria에 명시된 방식).
- `npm run lint`, TypeScript 컴파일(`tsc -b` 또는 기존 build 스크립트에 포함)
  통과 확인.

---

## 2. 완료 판정

- `npm run build` 성공(TypeScript strict 통과)
- `npm run lint` 통과
- `/` 라우트에서 기존 검색→상세→비교 플로우 회귀 없음
- `/admin/matches`, `/deals`, `/admin/coverage` 세 경로가 각각 빈 placeholder를
  정상 렌더링
- 커밋하지 않음 — 워킹트리 변경만

---

## 3. Executor Log (여기에 기록)
