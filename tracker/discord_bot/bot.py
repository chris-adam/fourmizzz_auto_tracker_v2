from typing import List

from discord_webhook import DiscordWebhook, DiscordEmbed

from discord_bot import models
from scraper.models import FourmizzzServer


def send_message(title:str, message: str, server: FourmizzzServer, color: str="03b2f8", webhook_urls: List=None):
    if webhook_urls is None:
        webhook_urls = models.DiscordWebhook.objects.filter(server=server).values_list("url", flat=True)

    webhooks = DiscordWebhook.create_batch(urls=webhook_urls, rate_limit_retry=True)

    # create embed object for webhook
    # you can set the color as a decimal (color=242424) or hex (color="03b2f8") number
    embed = DiscordEmbed(title=title, description=message, color=color)

    # add embed object to webhook
    for webhook in webhooks:
        webhook.add_embed(embed)

    return [webhook.execute() for webhook in webhooks]
