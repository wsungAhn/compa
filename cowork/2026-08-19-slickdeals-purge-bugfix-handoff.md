# Codex Handoff — 2026-08-19 · Slickdeals 게시물 48시간 보존 미적용 버그

> **상태(Status):** `대기 / pending`
>
> **작성자(Author):** Claude Sonnet 5 (랩탑 D:\dev\compa) → **수행자(Executor):** Codex CLI
> **작업명(Task):** `purge_expired_social_posts`가 `platform == "reddit"`로만
> 필터링돼 Slickdeals 게시물은 한 번도 삭제되지 않던 버그 수정.
> **발견 경위**: US-003(딜 피드) 라이브 검증 중 `compa.mwco.io/deals`에 4일
> 넘은 Slickdeals 딜이 노출됨을 발견. `ops/logs/worker.err.log` 확인 결과
> `reddit-purge-hourly`가 매시간 정상 실행되지만 항상 "0건 삭제"만 반환 —
> `backend/app/tasks/reddit_signals.py:23`의 `PLATFORM = "reddit"` 상수가
> `_purge()`(150-163행)의 `WHERE`절에 하드코딩돼 Slickdeals 행은 애초에
> 삭제 대상에서 빠져 있었음(추정: Slickdeals 추가 이전에 작성된 코드가
> 안 갱신됨).
> **범위(Scope)**: in — `backend/app/tasks/reddit_signals.py`의 `_purge()`
> WHERE절만. out — 다른 소셜 플랫폼(instagram/tiktok/facebook/naver_blog/
> xiaohongshu)의 보존 정책 — 이들은 US-006(보류 중) 파이프라인 소속이라
> 48시간 규칙 대상이 아니다, 건드리지 마라.

---

## 0. How to use this document

- **하지 마라:** 범위 밖 수정 · 커밋 · main 머지 · 서비스 재시작(리뷰어가
  검증 후 진행) · `.env` 변경
- **항상:** 수정 후 §3에 근거 기록.

## 1. 수정

`backend/app/tasks/reddit_signals.py`의 `_purge()`(150-163행):

```python
async def _purge() -> int:
    cutoff = now_utc() - timedelta(hours=RETENTION_HOURS)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(SocialPost).where(
                SocialPost.platform == PLATFORM,   # <- 버그: "reddit"만
                SocialPost.created_at < cutoff,
            )
        )
        ...
```

`SocialPost.platform == PLATFORM`을 `SocialPost.platform.in_(("reddit", "slickdeals"))`로
바꿔라(모듈 상수 `PLATFORM = "reddit"`은 다른 곳에서도 쓰이니 — 22행 근처
확인 — 그대로 두고, `_purge()`의 이 조건절만 바꿔라. 필요하면 새 상수
`_PURGED_PLATFORMS = ("reddit", "slickdeals")`를 만들어 써도 됨).

로그 메시지(162행 `"reddit: purged %d posts..."`)도 이제 두 플랫폼을
다루니 문구를 `"social posts: purged %d posts older than %dh (reddit+slickdeals)"`
정도로 정정해라(사소하지만 로그 읽는 사람이 헷갈리지 않게).

## 2. 완료 판정

- `mypy --strict app/` 0 errors
- 관련 테스트가 있으면 통과 확인, 없으면 이 함수를 직접 테스트하는 단위
  테스트 1개 추가 권장(reddit 게시물 + slickdeals 게시물 둘 다 만료
  상태로 만들어서 둘 다 삭제되는지 확인) — `backend/tests/tasks/` 기존
  파일 컨벤션 참고.
- `git status`로 이 파일(+ 신규 테스트 있으면 그 파일)만 바뀌었는지 확인.

## 3. Executor Log (여기에 기록)
