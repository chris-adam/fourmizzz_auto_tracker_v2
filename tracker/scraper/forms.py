from django.forms import ModelForm, PasswordInput
from django.core.exceptions import ValidationError

from scraper.models import FourmizzzServer, AllianceTarget, PlayerTarget
from scraper.web_agent import validate_fourmizzz_cookie_session, player_exists, get_alliance_members


class FourmizzzServerForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(FourmizzzServerForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            self.fields['name'].widget.attrs['readonly'] = True

    def clean_name(self):
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            return instance.name
        else:
            return self.cleaned_data['name']

    class Meta:
        model = FourmizzzServer
        fields = ('name', 'username', 'cookie_session')
        widgets = {'cookie_session': PasswordInput()}

    def clean(self):
        cleaned_data = super(FourmizzzServerForm, self).clean()
        if not validate_fourmizzz_cookie_session(cleaned_data['name'], cleaned_data['cookie_session']):
            raise ValidationError('Invalid cookie session, try to refresh your Fourmizzz tab')
        return self.cleaned_data


class AllianceTargetForm(ModelForm):
    class Meta:
        model = AllianceTarget
        fields = ('server', 'name')

    def clean(self):
        cleaned_data = super(AllianceTargetForm, self).clean()
        cookie_session = cleaned_data['server'].cookie_session
        if not get_alliance_members(cleaned_data['server'], cleaned_data['name'], cookie_session):
            raise ValidationError(f'Alliance {cleaned_data["name"]} not found in server {cleaned_data["server"]}')
        return self.cleaned_data


class PlayerTargetForm(ModelForm):
    class Meta:
        model = PlayerTarget
        fields = ('server', 'name')

    def clean(self):
        cleaned_data = super(PlayerTargetForm, self).clean()
        cookie_session = cleaned_data['server'].cookie_session
        if not player_exists(cleaned_data['server'], cleaned_data['name'], cookie_session):
            raise ValidationError(f'Player {cleaned_data["name"]} not found in server {cleaned_data["server"]}')
        return self.cleaned_data
