# fourmizzz_auto_tracker_v2

## Install deps

```bash
sudo apt install -y python3.11 gcc libpq-dev curl
# install docker
# install poetry
```

## Start the project

Run containers
```bash
docker compose up -d
```

Run Celery
```bash
poetry run celery -A tracker worker --loglevel=INFO --beat
```

Run Django
```bash
poetry run python3 manage.py runserver
```
