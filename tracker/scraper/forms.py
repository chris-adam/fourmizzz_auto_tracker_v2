from django.forms import ModelForm, PasswordInput
from django.core.exceptions import ValidationError

from scraper.models import FourmizzzCredentials, AllianceTarget, PlayerTarget
from scraper.web_agent import validate_fourmizzz_cookie_session, player_exists, get_alliance_members


class FourmizzzCredentialsForm(ModelForm):
    class Meta:
        model = FourmizzzCredentials
        fields = [f.name for f in FourmizzzCredentials._meta.get_fields()]
        widgets = {'cookie_session': PasswordInput()}

    def clean(self):
        cleaned_data = super(FourmizzzCredentialsForm, self).clean()
        if not validate_fourmizzz_cookie_session(cleaned_data['server'], cleaned_data['cookie_session']):
            raise ValidationError('Invalid cookie session')
        return self.cleaned_data


class AllianceTargetForm(ModelForm):
    class Meta:
        model = AllianceTarget
        fields = ('server', 'name')

    def clean(self):
        cleaned_data = super(AllianceTargetForm, self).clean()
        credentials = FourmizzzCredentials.objects.filter(server=cleaned_data['server']).first()
        if not credentials:
            raise ValidationError(f'Missing credentials for server {cleaned_data["server"]}')
        if not get_alliance_members(cleaned_data['server'], cleaned_data['name'], credentials.cookie_session):
            raise ValidationError(f'Alliance {cleaned_data["name"]} not found in server {cleaned_data["server"]}')
        return self.cleaned_data


class PlayerTargetForm(ModelForm):
    class Meta:
        model = PlayerTarget
        fields = ('server', 'name')

    def clean(self):
        cleaned_data = super(PlayerTargetForm, self).clean()
        credentials = FourmizzzCredentials.objects.filter(server=cleaned_data['server']).first()
        if not credentials:
            raise ValidationError(f'Missing credentials for server {cleaned_data["server"]}')
        if not player_exists(cleaned_data['server'], cleaned_data['name'], credentials.cookie_session):
            raise ValidationError(f'Player {cleaned_data["name"]} not found in server {cleaned_data["server"]}')
        return self.cleaned_data
