from django.contrib import admin

from discord_bot.models import DiscordWebhook
from discord_bot.forms import DiscordWebhookForm

@admin.register(DiscordWebhook)
class DiscordWebhookAdmin(admin.ModelAdmin):
    form = DiscordWebhookForm
    list_display = ('name', )
