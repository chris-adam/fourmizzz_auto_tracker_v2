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


async def migrate(request):
    """Temporaty route to migrate text channels to forums"""
    try:
        data = await request.json()
        category_name = data.get("category")

        guild = bot.get_guild(GUILD_ID)
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            return web.json_response({"message": "Category not found"}, status=404)

        for channel in category.text_channels:
            forum = discord.utils.get(category.forums, name=channel.name)
            if not forum:
                forum = await category.create_forum(name=channel.name)

            for thread in channel.threads:
                messages = [
                    m async for m in thread.history(limit=None, oldest_first=True)
                ]
                if not messages:
                    continue

                first_message = None
                while not first_message and messages:
                    first_message = messages.pop(0)
                    kwargs = {
                        "content": first_message.content,
                    }
                    if first_message.embeds:
                        kwargs["embed"] = first_message.embeds[0]
                    else:
                        first_message = None
                        continue
                if not first_message:
                    continue
                forum_thread = discord.utils.get(forum.threads, name=thread.name)
                if forum_thread is None:
                    archived_forum_threads = [t async for t in forum.archived_threads()]
                    forum_thread = discord.utils.get(
                        archived_forum_threads, name=thread.name
                    )
                if forum_thread is None:
                    forum_thread, _ = await forum.create_thread(
                        name=thread.name,
                        **kwargs,
                    )
                else:
                    await forum_thread.send(**kwargs)

                for message in messages:
                    kwargs = {}
                    if message.content:
                        kwargs["content"] = message.content
                    if message.embeds:
                        kwargs["embeds"] = message.embeds
                    else:
                        continue
                    if kwargs:
                        await forum_thread.send(**kwargs)

        return web.json_response({"message": "success"})
    except Exception as e:
        import traceback

        traceback.print_exc()
        return web.json_response({"message": str(e)}, status=500)


async def setup_http_server():
    app = web.Application()
    app.router.add_post("/post", post)
    app.router.add_post("/migrate", migrate)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", 5000)
    await site.start()


@bot.event
async def on_ready():
    await setup_http_server()


bot.run(TOKEN)
