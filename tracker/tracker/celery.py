import os

from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tracker.settings')

app = Celery('tracker')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'take-precision-snapshots-of-targets-every-minute': {
        'task': 'scraper.tasks.take_precision_snapshots',
        'schedule': crontab(minute='*'),
        # 'name': 'Take snapshots of targets every minute',
        'options': {
            'countdown': 4,
            'expires': 45,
            'priority': 9,  # highest priority
        },
    },
    'take-ranking-snapshots-every-minute': {
        'task': 'scraper.tasks.take_ranking_snapshots',
        'schedule': crontab(minute='*'),
        # 'name': 'Take snapshots of targets every minute',
        'options': {
            'countdown': 5,
            'expires': 45,
            'priority': 4,  # middle priority
        },
    },
    'process-snapshots-every-5-minutes': {
        'task': 'scraper.tasks.process_snapshots',
        'schedule': crontab(minute='*/5'),
        # 'name': 'Take snapshots of targets every minute',
        'options': {
            'expires': 240,
            'priority': 2,  # low priority
        },
    },
}
