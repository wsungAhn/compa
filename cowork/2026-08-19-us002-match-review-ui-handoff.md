# Codex Handoff — 2026-08-19 · US-002 매칭 검토 화면 구현

> **상태(Status):** `구현 완료 / implemented — build·lint·test 통과, browser smoke는 sandbox 제한으로 미수행`
>
> **작성자(Author):** Claude Sonnet 5 (랩탑 D:\dev\compa) → **수행자(Executor):** Codex CLI
> **작업명(Task):** `/admin/matches` placeholder를 실제 매칭 검토 화면으로 구현.
> **디자인 근거**: `designs/match-review/Match-Review.dc.html` — Claude Design이 만든
> 인터랙티브 프로토타입(디자인 시스템 확정본). **반드시 이 파일을 먼저 열어서(브라우저로
> 직접 열어도 되고 코드로 읽어도 됨) 레이아웃·색상·타이포·상태 전환을 그대로 참고할 것.**
> `support.js`는 그 프로토타입을 돌리는 자체 런타임(DC 프레임워크)이라 이식 대상이
> 아니다 — 이 파일이 보여주는 **디자인 스펙만** 가져오면 된다(React+실제 API로
> 재구현).
> **PRD 근거**: `docs/PRD-2026-08-07.md` §5 US-002, §6 FR-2.
> **선행 작업**: US-005(라우팅, 커밋 `5cc7ecf`)가 이미 랜딩돼 있음 —
> `frontend/src/routes/AdminMatchesPage.tsx`가 지금은 빈 placeholder.
> **범위(Scope)**: in — `AdminMatchesPage.tsx` 실제 구현, 관리자 시크릿 입력 훅
> 신설(`useAdminSecret`, `usePremium.ts` 패턴 재사용), `api/client.ts`에 매칭
> API 함수 3개 추가, Google Fonts(Space Grotesk, Instrument Sans) 로드. out —
> 백엔드 API 변경(기존 3개 엔드포인트 그대로 사용 — FR-2), 다른 페이지.

---

## 0. How to use this document (Executor, read first)

- **하지 마라:** 백엔드 `app/api/admin.py` 수정(FR-2 — 새 어드민 API 금지, 기존
  3개만 사용) · 범위 밖 리팩터 · 커밋 · main 머지 · 서비스 재시작 · `.env` 변경
- **항상:** 각 단계 후 빌드/린트 실행 → 통과 확인. §4에 기록.
- **디자인과 실제 데이터의 차이(중요, 아래 2절에 상세)**: 디자인 목업은 데모용
  가짜 데이터(KR/JP 가격 등)를 쓰지만, 실제 백엔드 API엔 없는 필드다. **없는
  데이터를 지어내지 마라** — 디자인의 시각적 틀(레이아웃·색·상태 전환·단축키)만
  가져오고, 데이터는 실제 API 응답 필드에 맞게 조정한다.

### Execution environment

- cwd: `frontend/` · Build: `npm run build` · Lint: `npm run lint` · Test: `npm run test`
- **npm install이 필요한 패키지 추가는 하지 마라** — axios 등 기존 의존성으로
  충분하다. 만약 정말 새 패키지가 필요하면(예상 없음) §4에 이유를 남기고 시도만
  해봐라 — 이 샌드박스는 npm registry 접근이 막혀 있을 수 있다(이전 라운드
  실측). 그 경우 리뷰어가 직접 설치한다.

---

## 1. 배경

이 화면은 관리자가 "자동 매칭 시스템이 같은 상품일 가능성이 있다고 판단한
두 국가 리스팅 쌍"을 승인/거절하는 큐다. 지금은 `curl`로 API를 직접 두드려야
하는데, 이걸 화면으로 만드는 게 US-002다.

## 2. 디자인 목업 vs 실제 API — 필드 매핑 (반드시 이대로 조정)

`designs/match-review/Match-Review.dc.html`의 seed 데이터는 `krBrand`, `krName`,
`krPrice`, `jpBrand`, `jpName`, `jpPrice`, `conf` 필드를 쓴다. 실제
`GET /api/admin/product-matches?status=pending`(`backend/app/api/admin.py`
`ProductMatchCandidateOut`)이 주는 필드는 다르다:

| 디자인 필드 | 실제 API 필드 | 처리 |
|---|---|---|
| `krBrand` / `jpBrand` | `brand` (하나만, orphan 기준) | 양쪽에 같은 `brand` 값을 표시하거나, 디자인의 "브랜드 두 줄" 레이아웃을 "브랜드 한 줄"로 단순화 — 판단은 구현자에게 맡기되 **없는 두 번째 브랜드값을 지어내지 마라** |
| `krName` | `orphan_name` (`orphan.name_jp` — 이름은 "KR"이지만 실제론 name_jp임에 주의, 변수명에 속지 말 것) | 그대로 매핑 |
| `jpName` | `canonical_name` (`canonical.name_en`) | 그대로 매핑 |
| `krPrice` / `jpPrice` | **없음** | 디자인의 가격 표시 줄 전체를 제거한다. 가격 정보는 이 API에 없다 — 지어내지 마라 |
| `conf` | `score` | 그대로 매핑(0~1 float로 가정, 디자인처럼 `Math.round(score*100)+'%'`) |
| 상단 "KR 리스팅 · Coupang" / "JP 리스팅 · Rakuten" 컬럼 헤더 | 플랫폼 정보 없음 | 플랫폼명 없이 "기존 표기" / "매칭 후보" 같은 중립적 라벨로 대체(정확한 문구는 구현자 재량 — 없는 플랫폼명을 지어내지만 마라) |
| `resolvedToday` (승인/거절 수), `approveRate` | **없음(서버 통계 API 없음)** | 서버에서 안 가져온다 — **이 페이지 방문 세션 동안 로컬로 누적**한다(0에서 시작, 화면에서 승인/거절할 때마다 클라이언트 상태로 증가). 디자인 데모의 `resolvedToday: 38` 같은 가짜 초기값은 쓰지 않는다 — 0부터 시작 |

디자인의 상태 전환 로직(대기→승인/거절, 그리고 **이미 처리된 항목 충돌 상태**)은
실제 API와 정확히 대응된다 — `approve`/`reject` 호출이 **409**를 반환하면
(`backend/app/api/admin.py` — 이미 `status != "pending"`이면 409) 디자인의
"conflict" 상태(`이미 처리된 항목 / 다른 운영자가 방금 해결했습니다` + 확인 버튼)를
그대로 쓴다. 이건 가짜 데이터가 아니라 실제 동시성 처리라 디자인 그대로 구현.

## 3. Task 목록

### T1 — 폰트 로드

`frontend/index.html`의 `<head>`에 디자인이 쓰는 Google Fonts 링크 추가
(Space Grotesk 400/500/600/700, Instrument Sans 400/500/600) — 디자인 파일
`<helmet>` 블록의 `<link>` 태그 그대로 가져오면 된다. 이 폰트는 이 페이지
전용으로 써도 되고, 사이트 전역에 영향 없게 스코프하고 싶으면 그렇게 판단해도 됨.

### T2 — `api/client.ts`에 매칭 API 함수 추가

기존 `setPremiumHeader` 패턴을 참고해 `setAdminSecretHeader(key)` 추가
(`X-Admin-Secret` 헤더). 그리고:
- `listProductMatches(status: 'pending' = 'pending'): Promise<ProductMatchCandidate[]>`
  — GET `/api/admin/product-matches`
- `approveProductMatch(id: string): Promise<void>` — POST
  `/api/admin/product-matches/{id}/approve`, 409는 예외로 던지되 호출부가
  구분할 수 있게(예: axios 에러의 status 코드로 판별)
- `rejectProductMatch(id: string): Promise<void>` — 동일 패턴

타입은 `ProductMatchCandidateOut` 스키마(`id`, `orphan_product_id`, `orphan_name`,
`canonical_product_id`, `canonical_name`, `brand`, `score`, `status`, `created_at`)
그대로 인터페이스로 정의.

### T3 — `useAdminSecret` 훅 신설

`frontend/src/hooks/usePremium.ts`를 그대로 본떠서(`localStorage` 키만
`compa-admin-secret` 등으로 바꿔서) 새 훅 작성. 화면 진입 시 저장된 시크릿이
없으면 입력 UI를 보여준다(`PremiumBanner.tsx` 스타일 참고 — 다만 이 페이지는
디자인 목업의 미니멀한 톤을 따르는 게 나으니 그 배너의 화려한 그라디언트 스타일을
그대로 복붙하지 말고, 인풋+버튼 정도로 단순하게).

### T4 — `AdminMatchesPage.tsx` 실제 구현

디자인 파일의 레이아웃·색상·타이포·상태를 그대로 옮긴다:
- 상단바(compa / Admin / 매칭 검토, 대기·오늘 처리·승인율 통계)
- 검토 대기열 헤더 + 컬럼 헤더
- 매칭 큐 리스트: 각 행 좌우 비교 레이아웃(가격 줄 제외 — 2절 참고), 신뢰도
  숫자+바(90% 이상 강조색, 미만 회색 — 디자인의 `low = conf < 0.8` 기준 그대로),
  승인/거절 버튼, 승인됨/거절됨 표시, 충돌 상태(409) 표시
- 빈 상태(대기열이 비었을 때)
- 키보드 단축키(↑↓ 이동, A 승인, R 거절) — 디자인의 `componentDidMount`
  keydown 핸들러 로직을 React `useEffect`로 이식
- 색상값 그대로 사용: 배경 `#fafafa`/`#ffffff`, 텍스트 `#111114`/`#71717a`/
  `#9a9aa3`, 보더 `#e4e4e7`/`#ececef`, 포인트 컬러 `#0E96C1`(호버 `#0B7A9E`)
- 실제 데이터 로딩: 페이지 마운트 시 `listProductMatches('pending')` 호출,
  로딩 중 상태 표시(디자인엔 없지만 실제 API 호출이 있으니 필요 — 심플하게)
- 에러 처리: 시크릿이 틀렸을 때(404 응답 — 백엔드가 인증 실패를 404로 감춤,
  `admin.py` 참고) 사용자에게 "시크릿을 확인해주세요" 정도로 안내

---

## 4. 완료 판정

- `npm run build` 성공, `npm run lint` 통과
- `/admin/matches` 접속 시 시크릿 미입력 상태면 입력 UI, 입력 후 실제 대기
  목록 로드
- 승인/거절 클릭 시 실제 API 호출 → 성공 시 디자인처럼 상태 전환(승인됨/거절됨
  표시 후 fade out), 409 시 충돌 상태 표시
- 빈 대기열일 때 빈 상태 화면
- 키보드 단축키(↑↓/A/R) 동작
- 회귀 없음: 다른 라우트(`/`, `/deals`, `/admin/coverage`)에 영향 없음
- 커밋하지 않음 — 워킹트리 변경만

---

## 5. Executor Log (여기에 기록)

- 2026-08-19 Codex:
  - `designs/match-review/Match-Review.dc.html`과 `docs/PRD-2026-08-07.md` §5 US-002/§6 FR-2를 읽고 구현 범위 확인.
  - 백엔드 `backend/app/api/admin.py`는 읽기만 수행. 수정 없음.
  - `frontend/index.html`: Space Grotesk / Instrument Sans Google Fonts 링크 추가.
  - `frontend/src/api/client.ts`: `setAdminSecretHeader`, `ProductMatchCandidate`, `listProductMatches`, `approveProductMatch`, `rejectProductMatch` 추가. 기존 `/api` baseURL에 맞춰 실제 호출 경로는 `/admin/product-matches...` 사용.
  - `frontend/src/hooks/useAdminSecret.ts`: `usePremium` 패턴으로 `compa-admin-secret` localStorage hook 추가.
  - `frontend/src/routes/AdminMatchesPage.tsx` + `AdminMatchesPage.css`: placeholder를 실제 매칭 검토 UI로 교체. 실제 API 필드만 사용했고 가격/플랫폼/서버 통계는 지어내지 않음. `brand`는 양쪽 동일 표시, `orphan_name`/`canonical_name` 매핑, `score` percent/bar 표시, 세션 로컬 처리 수/승인율 0부터 누적.
  - 상태 처리: 시크릿 미입력 UI, 로딩, 404 인증 오류 메시지, 409 conflict UI, 승인/거절 성공 표시 후 1.1초 뒤 제거, 빈 상태, ↑↓/A/R 단축키 구현.
  - 검증:
    - `npm run build` 통과. Vite chunk size warning은 기존 번들 크기 경고로 실패 아님.
    - `npm run lint` 통과.
    - `npm run test` 통과(9 tests).
  - Browser smoke:
    - `npm run dev -- --host 127.0.0.1 --port 5173` 시도했으나 sandbox 포트 listen 제한으로 `listen EPERM: operation not permitted 127.0.0.1:5173`.
    - Browser plugin/node_repl 초기화도 `sandboxCwd must be an absolute file URI` MCP 오류로 불가.
    - 기존 서비스 재시작은 지시대로 수행하지 않음.
  - 금지사항 준수: `npm install` 없음, 커밋 없음, `.env` 변경 없음, 백엔드 변경 없음, 서비스 재시작 없음.

## 6. Reviewer Log (Claude Sonnet 5, 2026-08-19)

빌드/린트/테스트 직접 재검증(build 성공, lint 통과, test 9/9 통과) 후
`compa.mwco.io/admin/matches`에 실제 브라우저로 접속해 확인:

- SPA fallback 수정(별도 핸드오프 `2026-08-19-spa-fallback-fix-handoff.md`)
  적용 후 API 서비스 재시작(`launchctl kickstart`) — 이제 `/admin/matches`
  직접 접속 시 404 JSON 대신 React 앱이 정상 렌더링됨.
- 디자인(`Match-Review.dc.html`) 대비 시각적 대조: 상단바 레이아웃(compa/Admin/
  매칭 검토), 대기·오늘처리·승인율 통계, "검토 대기열" 헤딩, 안내 문구, 색상/
  폰트 전부 일치.
- 관리자 시크릿 미입력 상태 UI 정상 표시(디자인엔 없던 화면이지만 자연스럽게
  같은 톤으로 추가됨).
- **알려진 제약**: 프로덕션 `.env`에 `ADMIN_SECRET`이 아예 설정 안 돼 있어
  (기존부터 있던 갭, 이번 작업과 무관) 실제 데이터 로드→승인/거절 흐름까지는
  라이브에서 검증 못 함 — 시크릿 값을 정하고 `.env`에 넣어야 완전한 E2E 확인
  가능. 코드 자체는 API 계약대로 올바르게 구현됨(코드 리뷰로 확인).

커밋 승인(US-002 + SPA fallback 둘 다).
