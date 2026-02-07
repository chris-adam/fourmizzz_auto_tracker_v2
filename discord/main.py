import asyncio
import os

from aiohttp import web

import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID"))

# Setup Bot
intents = discord.Intents.default()
intents.guilds = True  # Required to manage channels
intents.members = True  # Required to add users to threads
bot = commands.Bot(command_prefix="!", intents=intents)


async def post(request):
    try:
        data = await request.json()
        category_name = data.get("category")
        forum_name = data.get("forum")
        forum_id = await get_forum(category_name, forum_name)
        forum = bot.get_channel(forum_id)
        if not forum:
            return web.json_response({"message": "Forum not found"}, status=404)

        title = data.get("title")
        description = data.get("description")
        color = data.get("color", "03b2f8")
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.from_str(f"#{color}"),
        )

        silent = data.get("silent", False)
        thread_name = data.get("thread")
        thread_name = thread_name.lower().replace(" ", "-")
        thread = discord.utils.get(forum.threads, name=thread_name)
        if thread is None:
            archived_threads = [t async for t in forum.archived_threads()]
            thread = discord.utils.get(archived_threads, name=thread_name)
        if thread is None:
            thread, _ = await forum.create_thread(name=thread_name, embed=embed)
        else:
            await thread.send(embed=embed, silent=silent)
        # Add all guild members to the thread
        guild = bot.get_guild(GUILD_ID)
        thread_members = await thread.fetch_members()
        thread_members = [m.id for m in thread_members]
        for guild_member in guild.members:
            if not guild_member.bot and guild_member.id not in thread_members:
                while True:
                    try:
                        await thread.add_user(guild_member)
                        break
                    except discord.Forbidden:
                        break
                    except discord.errors.HTTPException:
                        await asyncio.sleep(5)

        return web.json_response({"message": "success"})
    except Exception as e:
        import traceback

        traceback.print_exc()
        return web.json_response({"message": str(e)}, status=500)


async def get_forum(category_name, forum_name):
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        raise Exception("Guild not found")

    forum_name = forum_name.lower().replace(" ", "-")

    category = discord.utils.get(guild.categories, name=category_name)
    if category is None:
        category = await guild.create_category(category_name)

    # Look for existing channel by normalized name
    forum = discord.utils.get(category.forums, name=forum_name)
    if forum is None:
        forum = await category.create_forum(name=forum_name)

    return forum.id


async def health(request):
    return web.json_response({"message": "success"})


async def setup_http_server():
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_post("/post", post)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", 5000)
    await site.start()


@bot.event
async def on_ready():
    await setup_http_server()


bot.run(TOKEN)
