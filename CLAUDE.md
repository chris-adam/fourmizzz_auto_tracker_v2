# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Fourmizzz Auto Tracker v2** is a Django + Celery web scraping application that monitors player statistics (hunting field, trophies, vacation/MV status) from the Fourmizzz browser game across servers s1–s4, and sends Discord notifications on detected changes.

## Development Commands

**Package manager:** UV (not pip or poetry)

```bash
# Install dependencies
uv sync

# Run Django dev server (from tracker/)
uv run python manage.py runserver

# Run Celery worker with beat scheduler (from tracker/)
uv run celery -A tracker worker --loglevel=INFO --beat

# Run migrations (from tracker/)
uv run python manage.py migrate

# Lint
uv run flake8 tracker/          # max-line-length=120
uv run isort tracker/           # force_single_line=True
```

**Infrastructure (PostgreSQL + RabbitMQ):**
```bash
docker compose up -d            # dev
docker compose -f docker-compose.prod.yml -p fourmizzz_auto_tracker_v2 up -d --build  # prod
```

**Production deployment** is handled by Jenkins (Jenkinsfile) on the `production` branch.

## Architecture

### Components

| Component | Location | Role |
|-----------|----------|------|
| Django app | `tracker/scraper/` | Models, views, admin, forms |
| Celery tasks | `tracker/scraper/tasks.py` | All business logic / scheduling |
| Web scraper | `tracker/scraper/web_agent.py` | HTTP scraping of fourmizzz.fr |
| Celery config | `tracker/tracker/celery.py` | Beat schedule, broker config |
| Discord bot | `discord/main.py` | aiohttp server (port 5000), posts notifications |
| Nginx | `docker/nginx/` | Reverse proxy, serves static files on port 8080 |

### Data Flow

1. **Celery Beat** triggers periodic tasks on schedule
2. **Precision snapshot tasks** scrape individual player pages → store `PrecisionSnapshot` with diffs
3. **Ranking snapshot tasks** scrape ranking pages → store `RankingSnapshot`, auto-adjust page count
4. **MV check task** (every 3s, priority 9) polls for vacation status changes
5. **Process snapshots task** (every 3min) correlates player movements with global ranking changes → POSTs to Discord bot at `:5000/post`
6. **Discord bot** creates per-server/alliance forum threads and sends rich embed messages

### Celery Task Schedule

| Task | Interval | Priority |
|------|----------|----------|
| `check-mv-players` | 3 seconds | 9 |
| `take-precision-snapshots` | 1 minute | 8 |
| `take-ranking-snapshots` | 1 minute | 4 |
| `process-snapshots` | 3 minutes | 2 |
| `clean-old-snapshots` | Daily 00:00 | 2 |

### Key Models (`tracker/scraper/models.py`)

- `FourmizzzServer` — server name (s1–s4), session cookie (`PHPSESSID`), `n_scanned_pages`
- `AllianceTarget` — alliance to monitor, linked to server
- `PlayerTarget` — player to track, linked to server + alliance, includes `mv` (vacation) flag
- `PrecisionSnapshot` — point-in-time player stats with diffs; `processed` flag used by process task
- `RankingSnapshot` — full ranking page snapshots with diffs

### Environment Files

- `postgres.env` — DB credentials
- `rabbitmq.env` — AMQP broker credentials
- `django.env` — Django secret key and allowed hosts
- `discord.env` — Discord bot token

## Notes

- **No tests** — `scraper/tests.py` is empty; testing is manual via Django admin
- Celery broker: RabbitMQ via AMQP; result backend: `django-db`
- Timezone: `Europe/Brussels`; task time limit: 30 seconds
- Snapshot retention: 3 days (cleaned by `clean-old-snapshots`)
- Ranking page count auto-scales based on the lowest tracked player's hunting field
- The Discord bot (`discord/`) is a separate Python project with its own `pyproject.toml` and UV lockfile
