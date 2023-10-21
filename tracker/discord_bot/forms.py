from django.forms import ModelForm, PasswordInput
from django.core.exceptions import ValidationError
from requests.exceptions import MissingSchema
from json import JSONDecodeError

from discord_bot.models import DiscordWebhook
from discord_bot.bot import send_message


class DiscordWebhookForm(ModelForm):
    class Meta:
        model = DiscordWebhook
        fields = ["name", "url"]
        widgets = {'url': PasswordInput()}

    def clean(self):
        cleaned_data = super(DiscordWebhookForm, self).clean()
        try:
            response = send_message("Webhook validation", "Validating webhook", "ffffff", [cleaned_data["url"]])[0]
        except (MissingSchema, JSONDecodeError) as e:
            raise ValidationError(f"Invalid webhook URL: {e}")
        if response.status_code >= 400:
            raise ValidationError(f"Invalid webhook URL: {response.content.decode('utf8')}")
        return self.cleaned_data
