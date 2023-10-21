#!/bin/sh

set -e

bash -c /opt/django/wait-for-postgres.sh

python manage.py showmigrations
python manage.py migrate

python -m gunicorn --bind 0.0.0.0:8000 tracker.wsgi:application --timeout 900 --workers=4
