# fourmizzz_auto_tracker_v2

This application watches player statistics (hunting field, trophies, vacation status) from the [Fourmizzz](http://fourmizzz.fr) browser game and automatically posts a message on your Discord server whenever something changes.

This guide explains how to install and run it on your own computer, **step by step, assuming no prior technical knowledge**. Expect the whole setup to take 30–60 minutes the first time.

## What you will need

- A computer (Windows, Mac or Linux) that stays powered on — the tracker only works while it is running.
- A Discord account, and a Discord server where you have the **Manage Server** permission (you can also [create a new server](https://support.discord.com/hc/en-us/articles/204849977) for free).
- A Fourmizzz account on the game server you want to watch.

## A quick word about the terminal

A few steps in this guide ask you to type commands in a **terminal** (also called a *command prompt* or *console*). It is just a window where you type text commands instead of clicking buttons — nothing more.

How to open one:

- **Windows**: press the Windows key, type `powershell`, press Enter. A blue/black window opens: that's your terminal.
- **Mac**: press `Cmd + Space`, type `terminal`, press Enter.
- **Linux**: press `Ctrl + Alt + T`, or look for "Terminal" in your applications menu.

To run a command: **copy it from this guide, paste it in the terminal window, and press Enter**. In many terminals, pasting is done with a right-click or `Ctrl + Shift + V` (`Cmd + V` on Mac). Then wait — some commands take a while and print a lot of text; that is normal. When the text stops and you see a line ending with `>` or `$` again, the command is finished.

## Step 1 — Install Docker

Docker is a free program that runs applications in self-contained boxes called *containers*. It lets you run this whole project (database, web server, Discord bot…) without installing each piece by hand.

- **Windows or Mac**: install [Docker Desktop](https://docs.docker.com/desktop/) (download it, run the installer, accept the defaults, restart if asked). After installing, **start Docker Desktop** and leave it running — the containers only work while Docker Desktop is open.
- **Linux**: follow the [Docker Engine installation guide](https://docs.docker.com/engine/install/) for your distribution.

To check that it works, open a terminal and run:

```bash
docker --version
```

If a version number appears (e.g. `Docker version 27...`), you're good. If you get an error like "command not found", Docker isn't installed correctly or Docker Desktop isn't started.

## Step 2 — Download the project

If you already have the project folder on your computer, skip to the "navigate" part below.

Otherwise, on the project's web page (where you are probably reading this), look for a green **Code** button and choose **Download ZIP**. Once downloaded, **extract** the ZIP file (right-click → "Extract all" on Windows, double-click on Mac) somewhere easy to find, e.g. your Documents folder.

Now open a terminal and **navigate into the project folder** with the `cd` command ("change directory"). For example, if the folder is in your Documents:

```bash
cd Documents/fourmizzz_auto_tracker_v2
```

> **Tip**: type `cd ` (with a space) and then drag-and-drop the project folder from your file explorer onto the terminal window — it fills in the path for you. Press Enter.

**All the commands in the rest of this guide must be run from inside this folder**, so keep this terminal window open. If you close it, open a new one and `cd` into the folder again.

## Step 3 — Create the Discord bot

The tracker sends its notifications through a Discord **bot**: a robot account that you create and that joins your server. You will get two pieces of information from this step: a **token** (the bot's password) and your **server ID**. Keep them somewhere handy (a notepad), you will need them in step 4.

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and log in with your Discord account. Click **New Application** (top right), give it a name (e.g. `Fourmizzz Tracker`) and click **Create**.
2. In the left menu, open the **Bot** tab:
   - Scroll down to **Privileged Gateway Intents** and turn on **Server Members Intent**, then click **Save Changes**. (The bot needs this to add your server's members to the notification threads.)
   - Scroll back up and click **Reset Token**, confirm, then **copy the token** and paste it in your notepad. ⚠️ The token is shown only once — if you lose it, come back here and reset it again. Never share it publicly: anyone with the token controls your bot.
3. In the left menu, open the **OAuth2** tab and scroll down to the **OAuth2 URL Generator**:
   - Under **Scopes**, check `bot`. A second panel of checkboxes appears below.
   - Under **Bot Permissions**, check:
     - **Manage Channels** (to create the notification channels)
     - **Manage Threads**
     - **Create Public Threads**
     - **Send Messages**
     - **Send Messages in Threads**
     - **Embed Links**
4. Copy the **Generated URL** at the very bottom of the page, paste it in your browser's address bar, and press Enter. Select the Discord server the bot should post in, click **Continue**, then **Authorize**. The bot now appears in your server's member list (offline for now — that's expected).
5. Get your **server ID**:
   - In Discord, open **User Settings** (the gear icon next to your name, bottom left) → **Advanced** → turn on **Developer Mode**.
   - Close the settings, **right-click your server's name** (top left) and click **Copy Server ID**. Paste it in your notepad.

## Step 4 — Configure the settings files

The project reads its settings (passwords, the bot token…) from four small text files ending in `.env`. The project ships with templates ending in `.env.example`; you first make a copy of each one, then fill in the blanks.

In your terminal (still inside the project folder), run these four commands to create the copies:

```bash
cp discord.env.example discord.env
cp django.env.example django.env
cp postgres.env.example postgres.env
cp rabbitmq.env.example rabbitmq.env
```

(`cp` simply means "copy". On Windows PowerShell, `cp` works too.)

Now open each `.env` file with a plain text editor — **Notepad** on Windows, **TextEdit** on Mac — and fill in the values after the `=` signs. For example, `DISCORD_TOKEN=` becomes `DISCORD_TOKEN=your-token-here`, with no spaces around the `=`.

> **Windows tip**: these files may not show up with a double-click. In Notepad, use *File → Open*, select "All files" in the file-type dropdown, and browse to the project folder.

Here is what to fill in, file by file:

| File | Line to fill | What to put there |
|------|--------------|-------------------|
| `discord.env` | `DISCORD_TOKEN=` | The bot token from step 3 |
| `discord.env` | `DISCORD_GUILD_ID=` | The server ID from step 3 |
| `django.env` | `SECRET_KEY=` | A long random string (see below) |
| `postgres.env` | `POSTGRES_PASSWORD=` | A password you invent (you won't have to remember it) |
| `rabbitmq.env` | `RABBITMQ_DEFAULT_PASS=` | Another password you invent (same, no need to remember it) |

For the `SECRET_KEY`, you need a long random string (it protects the web interface). Generate one by running this in your terminal:

```bash
docker run --rm python:3.11-slim python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Copy the random text it prints and paste it after `SECRET_KEY=`. (If you already have Python installed you can also run `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`.)

All the other lines in these files already have working values — leave them as they are. In particular, `HOST=localhost:8080` in `django.env` is correct for running on your own computer. Don't forget to **save** each file after editing.

## Step 5 — Start the application

Everything is configured; time to start it. In your terminal (inside the project folder, with Docker Desktop running), run:

```bash
docker compose -f docker-compose.prod.yml -p fourmizzz_auto_tracker_v2 up -d --build
```

The **first launch downloads and builds everything and can take 5–10 minutes** — a lot of text will scroll by, that's normal. It's done when you get your prompt back and see lines like `✔ Container fmz_tracker_django Started`.

This single command starts all the pieces of the tracker: the database, the web interface, the robots that scrape the game, and the Discord bot (which should now appear **online** in your Discord server).

To check that everything is running:

```bash
docker compose -f docker-compose.prod.yml -p fourmizzz_auto_tracker_v2 ps
```

You should see 7 lines with `Up` in the STATUS column.

## Step 6 — Create your administrator account

The tracker has a web interface where you tell it what to watch. Create your login for it by running:

```bash
docker compose -f docker-compose.prod.yml -p fourmizzz_auto_tracker_v2 exec django python manage.py createsuperuser
```

The terminal will ask you a few questions, one at a time — type your answer and press Enter:

- **Username**: pick anything (e.g. your name).
- **Email address**: optional, you can just press Enter.
- **Password**: type a password, press Enter, then type it again to confirm. ⚠️ **Nothing appears while you type the password** — not even `*` symbols. That's a security feature, your keystrokes are being registered: just type it and press Enter.

## Step 7 — Tell the tracker what to watch

Open [http://localhost:8080/admin](http://localhost:8080/admin) in your browser and log in with the account from step 6. (`localhost` means "this computer" — the page only exists on the machine running the tracker.)

### 7a. Add the game server

The tracker reads the game through a Fourmizzz account, so you need to hand it your game session:

1. In the admin, under **Scraper**, click **Fourmizzz servers**, then **Add Fourmizzz server** (top right).
2. Fill in:
   - **Name**: the game server to watch (`s1` to `s4`) — the one your account plays on.
   - **Username**: your Fourmizzz account name. This is just a reminder for yourself; it isn't used by the tracker.
   - **Cookie session**: this is the tricky one. It's a code stored in your browser that proves you're logged in to the game:
     1. Open [fourmizzz.fr](http://fourmizzz.fr) in your browser and log in to your account on the right server.
     2. Press `F12` to open the browser's developer tools.
     3. Go to the **Application** tab (Chrome/Edge) or **Storage** tab (Firefox), then **Cookies** → the fourmizzz address. ([Illustrated guide for Chrome](https://developer.chrome.com/docs/devtools/application/cookies/))
     4. Find the row named `PHPSESSID` and copy its **value** (a string of random letters and numbers) into the field.
     > If you later log out of the game in your browser, this code expires and the tracker stops working — just repeat this little procedure and update the field.
   - **Number of scanned pages**: leave the default (100); the tracker adjusts it by itself.
3. Click **Save**.

### 7b. Add the alliance to watch

1. Still under **Scraper**, click **Alliance targets**, then **Add alliance target**.
2. Choose the server you just created, and type the alliance name **exactly as it appears in the game** (capital letters matter).
3. Click **Save**. All current members of the alliance are automatically added as tracked players — you can see them under **Player targets**.

**That's it!** Within a few minutes, the tracker creates a channel in your Discord server named after the game server and alliance, and starts posting notifications there whenever a tracked player's stats change.

## Everyday use

All these commands are run from a terminal, inside the project folder.

**Stop the tracker:**

```bash
docker compose -f docker-compose.prod.yml -p fourmizzz_auto_tracker_v2 down
```

**Start it again** (no need to redo the setup, your configuration is kept):

```bash
docker compose -f docker-compose.prod.yml -p fourmizzz_auto_tracker_v2 up -d --build
```

**See what's happening behind the scenes** (useful when something doesn't work — press `Ctrl + C` to stop watching):

```bash
docker compose -f docker-compose.prod.yml -p fourmizzz_auto_tracker_v2 logs -f
```

## Update to the latest version

When a new version of the tracker is published, here is how to switch to it. **Your settings and tracked players are safe**: they live in the database, which is kept across updates — you will NOT have to redo the setup.

**If you downloaded the project as a ZIP** (like in step 2):

1. Download the new ZIP from the project page (green **Code** button → **Download ZIP**) and extract it, e.g. next to the old folder.
2. Copy your four settings files — `discord.env`, `django.env`, `postgres.env` and `rabbitmq.env` — from the old folder into the new one (they are not included in the ZIP, they are yours).
3. Open a terminal, `cd` into the **new** folder, and run the usual start command:

   ```bash
   docker compose -f docker-compose.prod.yml -p fourmizzz_auto_tracker_v2 up -d --build
   ```

   This rebuilds what changed and restarts the tracker on the new version. Once it runs, you can delete the old folder.

> **Can't see the `.env` files when copying?** Files starting or ending in `.env` are sometimes hidden. In the Windows file explorer, enable *View → Show → File name extensions* and *Hidden items*; on Mac press `Cmd + Shift + .` in Finder.

**If you use git** (for the more technical): from the project folder, run `git pull`, then the same `docker compose ... up -d --build` command.

## If something goes wrong

- **`docker: command not found`** → Docker isn't installed (step 1), or Docker Desktop isn't started.
- **`no configuration file provided` or `not found`** → your terminal isn't inside the project folder; redo the `cd` from step 2.
- **The bot stays offline in Discord** → check `DISCORD_TOKEN` in `discord.env` (no extra spaces, complete token), then restart the tracker (stop + start commands above).
- **No notifications arrive** → the game session may have expired; update the **Cookie session** field as explained in step 7a. Also check that the bot has the permissions from step 3 on your server.
- **The page `localhost:8080` doesn't load** → make sure the containers are running (`ps` command in step 5) and that you started them on this same computer.
