"""재시도 상한 검증 — 크레딧 전소 사고의 ③번 루프 회귀 방지.

retry_count는 증가만 하고 상한이 없어서, 영영 매칭 안 되는 포스트가 매시간
extractor(LLM)를 재호출했다. 상한 도달 시 반드시 영구 실패(processed=True,
failed=True)로 전이해 선택 쿼리(processed IS FALSE)에서 빠져야 한다.
"""
from app.ai.pipeline import MAX_EXTRACT_ATTEMPTS, _mark_retryable
from app.models.social_post import SocialPost


def _post(retry_count: int) -> SocialPost:
    return SocialPost(platform="reddit", content="x", retry_count=retry_count)


def test_below_cap_stays_retryable() -> None:
    post = _post(retry_count=0)
    _mark_retryable(post, "extract failed: APIError")
    assert post.processed is False
    assert post.failed is False
    assert post.retry_count == 1


def test_cap_transitions_to_permanent_failure() -> None:
    post = _post(retry_count=MAX_EXTRACT_ATTEMPTS - 1)
    _mark_retryable(post, "extract failed: APIError")
    # 영구 실패 = 큐에서 이탈. 이 두 플래그 중 하나라도 풀리면 무한 루프가 부활한다.
    assert post.processed is True
    assert post.failed is True
    assert post.retry_count == MAX_EXTRACT_ATTEMPTS
    assert "retry limit" in (post.last_error or "")


def test_loop_always_drains() -> None:
    """상한이 얼마든, 반복 호출은 유한 번 안에 반드시 큐를 이탈한다."""
    post = _post(retry_count=0)
    for _ in range(MAX_EXTRACT_ATTEMPTS + 1):
        if post.processed:
            break
        _mark_retryable(post, "no extracted events")
    assert post.processed is True
