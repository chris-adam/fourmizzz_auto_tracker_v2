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


async def message(request):
    try:
        data = await request.json()
        category_name = data.get("category")
        channel_name = data.get("channel")
        channel_id = await get_channel(category_name, channel_name)
        channel = bot.get_channel(channel_id)
        if not channel:
            return web.json_response({"message": "Channel not found"}, status=404)

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
        if thread_name:
            thread_name = thread_name.lower().replace(" ", "-")
            thread = discord.utils.get(channel.threads, name=thread_name)
            if thread is None:
                archived_threads = [t async for t in channel.archived_threads()]
                thread = discord.utils.get(archived_threads, name=thread_name)
            if thread is None:
                thread = await channel.create_thread(name=thread_name)
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
            await thread.send(embed=embed, silent=silent)
        else:
            await channel.send(embed=embed, silent=silent)

        return web.json_response({"message": "success"})
    except Exception as e:
        import traceback

        traceback.print_exc()
        return web.json_response({"message": str(e)}, status=500)


async def get_channel(category_name, channel_name):
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        raise Exception("Guild not found")

    channel_name = channel_name.lower().replace(" ", "-")

    category = discord.utils.get(guild.categories, name=category_name)
    if category is None:
        category = await guild.create_category(category_name)

    # Look for existing channel by normalized name
    channel = discord.utils.get(category.text_channels, name=channel_name)
    if channel is None:
        channel = await category.create_text_channel(name=channel_name)

    return channel.id


async def setup_http_server():
    app = web.Application()
    app.router.add_post("/message", message)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", 5000)
    await site.start()


@bot.event
async def on_ready():
    await setup_http_server()


bot.run(TOKEN)
