#!/bin/sh

# Stop script on error
set -e

# Wait for PostgreSQL
bash -c /opt/django/wait-for-postgres.sh

# Django migrations
python manage.py showmigrations
python manage.py migrate

# Purge old tasks
python -m celery -A tracker purge -f
python manage.py shell -c "
import datetime
from scraper.models import PrecisionSnapshot, RankingSnapshot
cutoff = datetime.datetime.now() - datetime.timedelta(days=3)
p = PrecisionSnapshot.objects.filter(time__lt=cutoff).delete()
r = RankingSnapshot.objects.filter(time__lt=cutoff).delete()
print('Deleted:', p, r)
"

# Start server
python -m gunicorn --bind 0.0.0.0:8000 tracker.wsgi:application --timeout 900 --workers=4
