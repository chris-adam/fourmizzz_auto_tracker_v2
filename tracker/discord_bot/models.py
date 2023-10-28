from django.db import models
from django.utils.html import format_html

from scraper.models import FourmizzzServer

class DiscordWebhook(models.Model):
    server = models.ForeignKey(FourmizzzServer, on_delete=models.CASCADE)
    name = models.fields.CharField(max_length=100, default="Captain Hook")
    url = models.fields.CharField(max_length=200, help_text=format_html("<a target='_blank' rel='noopener' href='https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks'>How to make a webhook</a>"))

    def __str__(self) -> str:
        return self.name
