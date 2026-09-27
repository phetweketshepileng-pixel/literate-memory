"""Celery app factory. Queues are isolated per the V1.1 architecture
review: ai_heavy (match scoring, CV tailoring, message generation),
scraping (job ingestion), default (analytics, notifications) — so a slow
AI provider or a stuck scraper never starves the others."""
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "ai_job_hunter",
    broker=settings.REDIS_BROKER_URL,
    backend=settings.REDIS_BROKER_URL,
    include=[
        "app.workers.match_scoring_tasks",
        "app.workers.cv_tailoring_tasks",
        "app.workers.job_scraper_tasks",
        "app.workers.analytics_tasks",
        "app.workers.recruiter_intelligence_tasks",
    ],
)

celery_app.conf.task_routes = {
    "match_scoring.*": {"queue": "ai_heavy"},
    "cv_tailoring.*": {"queue": "ai_heavy"},
    "message_generation.*": {"queue": "ai_heavy"},
    "job_discovery.*": {"queue": "scraping"},
    "analytics.*": {"queue": "default"},
    "recruiter_intelligence.*": {"queue": "default"},
}

celery_app.conf.beat_schedule = {
    "materialize-analytics-nightly": {
        "task": "analytics.materialize_all_snapshots",
        "schedule": 86400.0,  # once/day; production uses crontab(hour=2, minute=0)
    },
    "materialize-recruiter-intelligence-weekly": {
        "task": "recruiter_intelligence.materialize_all",
        # weekly, not daily — recruiter/company behavior is a slow-moving
        # signal (ai-job-hunter-recruiter-intelligence.md section 4), and
        # k-anonymity-gated aggregates don't shift meaningfully day to day
        "schedule": 604800.0,  # production uses crontab(day_of_week=0, hour=3)
    },
}

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
