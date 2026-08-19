# Codex Handoff — 2026-08-19 · SPA 클라이언트 라우팅 404 수정 (US-005 후속 버그)

> **상태(Status):** `완료 / done`
>
> **작성자(Author):** Claude Sonnet 5 (랩탑 D:\dev\compa) → **수행자(Executor):** Codex CLI
> **작업명(Task):** `backend/app/main.py`의 정적 파일 서빙이 `/`만 `index.html`을
> 서빙하고 `/admin/matches` 같은 client-side 라우트는 404를 반환하는 문제 수정.
> **발견 경위**: US-005(react-router 도입, 커밋 `5cc7ecf`) 이후 US-002 구현을
> 실제 라이브(`compa.mwco.io/admin/matches`)에서 브라우저로 확인하다 발견 —
> `{"detail":"Not Found"}` JSON 응답. `/`만 쓰던 시절엔 안 드러났던 갭.
> **범위(Scope)**: in — `backend/app/main.py`의 정적 파일 마운트 부분만. out —
> 다른 로직 변경.

---

## 0. How to use this document (Executor, read first)

- **하지 마라:** 범위 밖 수정 · 커밋 · main 머지 · 서비스 재시작(`launchctl kickstart`
  등 — 이 작업은 워킹트리 변경 후 리뷰어가 검증·재시작까지 진행) · `.env` 변경
- **항상:** 수정 후 최소한 코드 리뷰 가능한 형태로 남기고 §3에 근거를 기록.

---

## 1. 문제

`backend/app/main.py:77-79`:
```python
_DIST = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
```

Starlette `StaticFiles(html=True)`는 요청 경로가 **디렉토리**일 때만
`index.html`을 대신 서빙한다. `/admin/matches`, `/deals`, `/admin/coverage`처럼
실제 파일/디렉토리가 없는 client-side 라우트 경로는 그냥 404가 난다 — 브라우저에서
그 URL로 직접 접속하거나 새로고침하면 React 앱이 아니라 FastAPI의 JSON 404
응답이 뜬다(SPA 안에서 `<Link>` 클릭으로 이동할 땐 문제없음 — 브라우저
새로고침·직접 URL 접속·북마크에서만 발생).

## 2. 수정 방향

`StaticFiles`를 그대로 쓰되, 매칭되는 정적 파일이 없을 때(404) `index.html`로
폴백하는 서브클래스로 교체한다. 표준적으로 널리 쓰이는 패턴이다:

```python
from starlette.types import Scope

class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        if response.status_code == 404:
            response = await super().get_response("index.html", scope)
        return response
```

그리고 `app.mount("/", StaticFiles(...))` → `app.mount("/", SPAStaticFiles(...))`로
교체.

**주의할 것**:
1. 이 마운트는 `/api/*` 라우터들이 먼저 등록된 뒤에 와야 한다(현재도 그런
   순서일 가능성이 높음 — `main.py`에서 라우터 include 순서 확인하고, 이
   `SPAStaticFiles` 마운트가 반드시 API 라우터들보다 뒤에 오는지 재확인해라.
   먼저 오면 `/api/*` 요청까지 이 마운트가 가로채서 API가 전부 깨진다).
2. 진짜 존재하지 않는 정적 에셋 요청(예: `/assets/typo-in-filename.js`)도
   이제 index.html로 폴백되는데, 이건 SPA 배포의 일반적인 트레이드오프라
   허용 범위다 — 별도 처리 불필요.
3. `_DIST.exists()`가 false인 경우(dist가 없는 개발 환경)의 기존 동작은
   그대로 유지.

## 3. 완료 판정

- 로컬에서 `python -c`로 앱을 띄우지 않고, 코드 리뷰 수준에서 위 로직이
  올바른지 확인(실제 서버 기동/재시작은 리뷰어가 함).
- 기존 `/api/*` 라우팅에 영향 없는지 라우터 등록 순서 코드로 확인.
- 이 파일 하나만 바뀌었는지 `git status` 확인.

---

## 4. Executor Log (여기에 기록)

- 2026-08-19 Codex: 작업 시작. `review-tiers.md` 기준 단일 파일 버그픽스라 Tier 1로 판단.
- 2026-08-19 Codex: `backend/app/main.py` 확인. API 라우터와 `/health`가 정적 파일 mount보다 먼저 등록되어 있어 `/api/*` 라우팅 선점 위험은 현재 순서상 없음.
- 2026-08-19 Codex: 로컬 Starlette `StaticFiles.get_response()` 구현 확인. 이 버전은 미매칭 경로에서 404 `Response`를 반환하지 않고 `HTTPException(status_code=404)`를 raise하므로, SPA fallback은 404 예외를 catch해 `index.html`을 재조회하는 방식으로 구현 예정.
- 2026-08-19 Codex: `SPAStaticFiles` 추가 후 `/` 정적 mount를 `StaticFiles`에서 `SPAStaticFiles`로 교체. `_DIST.is_dir()` guard와 라우터 등록 순서는 유지.
- 2026-08-19 Codex: 검증 완료. `PYTHONPATH=. python -m py_compile app/main.py` 성공(출력: `pyenv: cannot rehash: /Users/Mung/.pyenv/shims isn't writable`, exit 0). 서버 기동/서비스 재시작/커밋은 하지 않음.
- 2026-08-19 Codex: `git status --short` 확인. 이번 작업 변경 파일은 `backend/app/main.py`, `cowork/2026-08-19-spa-fallback-fix-handoff.md`; 그 외 `cowork/2026-08-19-us002-match-review-ui-handoff.md`, `frontend/*` 변경은 작업 전부터 존재한 별도 변경으로 판단해 건드리지 않음.
