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
    'take-snapshots-of-targets-every-minute': {
        'task': 'scraper.tasks.take_snapshot',
        'schedule': crontab(minute='*'),
        # 'name': 'Take snapshots of targets every minute',
        'options': {
            'countdown': 10,
            'expires': 30,
        },
    },
}
