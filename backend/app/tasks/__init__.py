"""Celery app configuration and task registration."""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery = Celery("app")

# Configure broker and result backend
celery.conf.update(
    broker_url=settings.redis_url,
    result_backend=settings.redis_url,
    timezone="Asia/Seoul",
    enable_utc=True,
    include=[
        "app.tasks.collect",
        "app.tasks.classify",
        "app.tasks.match_products",
        "app.tasks.cleanup",
        "app.tasks.social_collect",
        "app.tasks.social_extract",
        "app.tasks.seed",
        "app.tasks.reddit_signals",
    ],
    beat_schedule={
        "collect-all-daily": {
            "task": "app.tasks.collect.collect_all_products",
            "schedule": crontab(hour=3, minute=0),
        },
        "classify-pending-hourly": {
            "task": "app.tasks.classify.classify_pending",
            "schedule": crontab(minute=15),
        },
        "social-collect-6h": {
            "task": "app.tasks.social_collect.collect_social_for_products",
            "schedule": crontab(hour="*/6", minute=30),
        },
        # 저빈도 — 무인증 RSS라 하루 24회면 충분하고, 팬아웃은 429를 부른다.
        "reddit-signals-hourly": {
            "task": "app.tasks.reddit_signals.collect_reddit_signals",
            "schedule": crontab(minute=5),
        },
        # Slickdeals는 Reddit 같은 무인증 한도가 없어 조금 더 자주 봐도 된다.
        "slickdeals-signals": {
            "task": "app.tasks.reddit_signals.collect_slickdeals_signals",
            "schedule": crontab(minute="25,55"),
        },
        # 48시간 보존 강제. 수집과 같은 주기라 최대 체류가 한도를 넘지 않는다.
        "reddit-purge-hourly": {
            "task": "app.tasks.reddit_signals.purge_expired_social_posts",
            "schedule": crontab(minute=50),
        },
        "social-extract-hourly": {
            "task": "app.tasks.social_extract.extract_social_posts",
            "schedule": crontab(minute=45),
        },
        "match-products-6h": {
            "task": "app.tasks.match_products.match_pending_products",
            "schedule": crontab(minute=40, hour="*/6"),
        },
        # 이벤트 0개로 24h 넘게 방치된 고아 product 정리 (언어 무관, JP 매칭과 무관).
        "cleanup-empty-orphans-daily": {
            "task": "app.tasks.cleanup.cleanup_empty_orphan_products",
            "schedule": crontab(hour=4, minute=0),
        },
    },
)
