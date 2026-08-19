# Codex Handoff — 2026-08-19 · naver_blog.py를 NAVER API HUB로 이관

> **상태(Status):** `완료 / done`
>
> **작성자(Author):** Claude Sonnet 5 (랩탑 D:\dev\compa) → **수행자(Executor):** Codex CLI
> **작업명(Task):** `backend/app/social/naver_blog.py`가 아직 구 네이버 검색 API
> (`openapi.naver.com`, `X-Naver-Client-Id`/`Secret`)를 쓰고 있는데, 이 API는
> 2026-06-29 종료 공지됐고 NAVER API HUB(네이버 클라우드 플랫폼)로 이관됐다.
> 블로그 검색은 이관 대상에 포함되므로(`docs/scrapers.md` 이관표 확인) 새
> 도메인/인증 헤더로 코드를 갱신한다.
> **근거 문서**: `docs/scrapers.md`의 "네이버 검색 API 종료 → NAVER API HUB
> 이관" 절 — 이관 계약표를 그대로 따를 것.
> **범위(Scope)**: in — `backend/app/social/naver_blog.py`(엔드포인트·헤더),
> `backend/app/core/config.py`(설정 필드명 갱신). out — `naver_shop.py`(쇼핑
> 검색은 이관 대상 자체가 아님 — 별도 문제, 건드리지 마라), 다른 소셜 수집기.

---

## 0. How to use this document

- **하지 마라:** `naver_shop.py` 수정 · 범위 밖 리팩터 · 커밋 · main 머지 ·
  서비스 재시작 · `.env` 값 임의 설정(실제 키는 사용자가 발급받아 넣는다)
- **항상:** 수정 후 §3에 근거 기록.

## 1. 이관 계약 (docs/scrapers.md 표 그대로)

| 항목 | 기존 (죽어가는 것, 쓰면 안 됨) | NAVER API HUB (새로 써야 하는 것) |
|---|---|---|
| 도메인 | `openapi.naver.com` | `naverapihub.apigw.ntruss.com` |
| 경로 | `/v1/search/blog.json` | `/search/v1/blog` |
| 인증 헤더 | `X-Naver-Client-Id` / `X-Naver-Client-Secret` | `X-NCP-APIGW-API-KEY-ID` / `X-NCP-APIGW-API-KEY` |
| 키 | 기존 키 사용 불가 | NCP 콘솔(`console.ncloud.com`)에서 신규 발급 필요 |

## 2. 수정 사항

### 2-1. `backend/app/core/config.py`

`naver_client_id`/`naver_client_secret` 필드명을 새 체계에 맞게 정정한다
(예: `ncp_api_key_id`, `ncp_api_key` — 정확한 이름은 프로젝트 네이밍 관례를
따르되, 옛 이름을 그대로 쓰면 나중에 "NCP 키인데 naver_client라는 이름"이라
헷갈리니 새 이름으로 바꾸는 걸 권장). `grep -rn "naver_client_id\|naver_client_secret"`로
다른 소비처가 있는지 재확인해라(현재 확인 결과 `naver_blog.py` 단 한 곳뿐이지만,
너의 워킹트리 기준으로 다시 확인).

### 2-2. `backend/app/social/naver_blog.py`

`NaverBlogCollector.collect()`(현재 66-93행 부근):
- `settings.naver_client_id`/`naver_client_secret` 참조를 2-1에서 정한 새
  필드명으로 교체.
- 요청 헤더를 `X-NCP-APIGW-API-KEY-ID`/`X-NCP-APIGW-API-KEY`로 교체.
- 요청 URL을 `https://naverapihub.apigw.ntruss.com/search/v1/blog`로 교체.
- 파라미터(`query`, `display`, `sort`)와 응답 파싱(`parse_response()`)은
  API HUB도 동일한 응답 스키마를 유지한다고 가정하고 **그대로 둔다** — 다만
  이건 가정이라, 완료 판정에서 실제 응답으로 검증 필요(아래 참고).

### 2-3. `.env.example` 갱신

`NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET` 항목이 있다면 새 이름·새 발급처
안내(`console.ncloud.com`)로 주석 갱신.

## 3. Executor Log (여기에 기록)

- 2026-08-19 Codex: 시작. `docs/scrapers.md` 이관 계약 확인. `rg` 및 knowledge graph 조회로
  old Naver Developers 키 소비처가 `backend/app/core/config.py`,
  `backend/app/social/naver_blog.py`뿐임을 확인. `naver_shop.py`는 범위 밖으로 유지.
- 2026-08-19 Codex: `Settings` 필드를 `ncp_api_key_id`/`ncp_api_key`로 변경,
  `NaverBlogCollector` 요청 URL을 `https://naverapihub.apigw.ntruss.com/search/v1/blog`로
  변경, 인증 헤더를 `X-NCP-APIGW-API-KEY-ID`/`X-NCP-APIGW-API-KEY`로 변경.
  `.env.example`은 NCP Console 발급 키 이름으로 갱신.
- 2026-08-19 Codex: `tests/social/test_naver_blog.py`에 API HUB URL/헤더/파라미터
  계약 테스트와 키 누락 시 네트워크 미호출 테스트 추가.
- 2026-08-19 Codex: 검증 완료.
  `backend/.venv/bin/pytest tests/social/test_naver_blog.py tests/core/test_config.py` →
  17 passed. `backend/.venv/bin/mypy --strict app/` → Success, 88 source files
  (`pyenv rehash` warning은 있었으나 exit 0). `backend/.venv/bin/pytest` →
  523 passed, 1 skipped. `git diff --name-only` 범위는 `.env.example`,
  `backend/app/core/config.py`, `backend/app/social/naver_blog.py`,
  `backend/tests/social/test_naver_blog.py`, 이 handoff 문서뿐.

---

## 4. 완료 판정 (일부는 실제 키 발급 후 리뷰어가 최종 확인)

- `mypy --strict app/` 0 errors
- 기존 pytest 회귀 없음(`naver_blog.py` 관련 테스트 있으면 mock 응답 스키마도
  같이 갱신)
- `git status`로 범위(2-1, 2-2, 2-3) 밖 파일 변경 없는지 확인
- **(리뷰어가 나중에 실제 NCP 키로 검증)**: 실제 API 호출이 200과 함께
  `items` 배열을 반환하는지 — 응답 스키마가 구 API와 다르면 `parse_response()`
  추가 조정 필요할 수 있음을 인지하고 있을 것
