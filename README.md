# fourmizzz_auto_tracker_v2

Django + Celery application that monitors player statistics (hunting field, trophies, vacation status) from the [Fourmizzz](http://fourmizzz.fr) browser game and sends Discord notifications on detected changes.

## Run the project in prod mode (locally)

### 1. Create the Discord bot

The tracker posts its notifications to a Discord server through a bot, so you need to create one first.

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and click **New Application**, give it a name (e.g. `Fourmizzz Tracker`).
2. In the left menu, open the **Bot** tab:
   - Under **Privileged Gateway Intents**, enable **Server Members Intent** (the bot needs it to add members to notification threads).
   - Click **Reset Token**, then copy the token. This is the value for `DISCORD_TOKEN` (you will need it in the next section). The token is only shown once — if you lose it, reset it again.
3. In the **OAuth2** tab, scroll to the **OAuth2 URL Generator**:
   - Under **Scopes**, check `bot`.
   - Under **Bot Permissions**, check:
     - **Manage Channels** (creates the category and forum channels)
     - **Manage Threads**
     - **Create Public Threads**
     - **Send Messages**
     - **Send Messages in Threads**
     - **Embed Links**
4. Copy the generated URL at the bottom, open it in your browser, select the Discord server you want the bot to post in, and click **Authorize**. You must have the **Manage Server** permission on that server.
5. Get the server (guild) ID: in Discord, go to **User Settings → Advanced** and enable **Developer Mode**, then right-click your server's name and click **Copy Server ID**. This is the value for `DISCORD_GUILD_ID`.

### 2. Configure the environment files

Copy each `*.env.example` file to its `*.env` counterpart:

```bash
for f in *.env.example; do cp "$f" "${f%.example}"; done
```

Then fill in the required variables:

| File | Variable | Value |
|------|----------|-------|
| `discord.env` | `DISCORD_TOKEN` | The bot token from step 1 |
| `discord.env` | `DISCORD_GUILD_ID` | The server ID from step 1 |
| `django.env` | `SECRET_KEY` | A random secret (see command below) |
| `django.env` | `HOST` | Host serving the app, `localhost:8080` when running locally |
| `postgres.env` | `POSTGRES_PASSWORD` | Any password of your choice |
| `rabbitmq.env` | `RABBITMQ_DEFAULT_PASS` | Any password of your choice |

Generate a secret key with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

The other variables in the env files have working defaults and can be left as is.

### 3. Start the containers

You need Docker with the Compose plugin — see the [Docker installation guide](https://docs.docker.com/engine/install/) and the [Compose documentation](https://docs.docker.com/compose/).

```bash
docker compose -f docker-compose.prod.yml -p fourmizzz_auto_tracker_v2 up -d --build
```

This starts PostgreSQL, RabbitMQ, the Django app (migrations run automatically on startup), the two Celery workers, the Discord bot and Nginx. The web interface is served on port **8080**.

### 4. Create a Django superuser

```bash
docker compose -f docker-compose.prod.yml -p fourmizzz_auto_tracker_v2 exec django python manage.py createsuperuser
```

Follow the prompts to choose a username and password.

### 5. Configure the tracker

Log in to the Django admin at [http://localhost:8080/admin](http://localhost:8080/admin) with the superuser you just created, then:

1. **Add a Fourmizzz server** (*Scraper → Fourmizzz servers → Add*):
   - **Name**: the game server to scrape (`s1` to `s4`).
   - **Username**: the game account the session cookie belongs to (only for your own reference).
   - **Cookie session**: the value of the `PHPSESSID` cookie from a logged-in fourmizzz.fr session on that server ([how to inspect cookies in Chrome DevTools](https://developer.chrome.com/docs/devtools/application/cookies/)).
   - **Number of scanned pages**: how many ranking pages to scrape; the default of 100 is fine, it auto-adjusts afterwards.
2. **Add an alliance target** (*Scraper → Alliance targets → Add*): pick the server you just created and enter the alliance name exactly as it appears in game. On save, all current members of the alliance are automatically added as tracked players (visible under *Scraper → Player targets*).

The Celery workers will start scraping the tracked players right away, and notifications will appear in your Discord server in a category/forum named after the server and alliance.
