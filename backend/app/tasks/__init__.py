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
    include=["app.tasks.collect", "app.tasks.classify"],
    beat_schedule={
        "collect-all-daily": {
            "task": "app.tasks.collect.collect_all_products",
            "schedule": crontab(hour=3, minute=0),
        },
        "classify-pending-hourly": {
            "task": "app.tasks.classify.classify_pending",
            "schedule": crontab(minute=15),
        },
    },
)
