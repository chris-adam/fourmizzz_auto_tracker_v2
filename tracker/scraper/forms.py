from django.forms import ModelForm, PasswordInput
from django.core.exceptions import ValidationError

from scraper.models import FourmizzzCredentials, AllianceTarget, PlayerTarget
from scraper.web_agent import validate_fourmizzz_credentials, validate_fourmizzz_cookie_session


class FourmizzzCredentialsForm(ModelForm):
    class Meta:
        model = FourmizzzCredentials
        fields = [f.name for f in FourmizzzCredentials._meta.get_fields()]
        widgets = {
            'password': PasswordInput(),
            'cookie_session': PasswordInput(),
        }

    def clean(self):
        cleaned_data = super(FourmizzzCredentialsForm, self).clean()
        if not validate_fourmizzz_cookie_session(self.cleaned_data['server'], self.cleaned_data['cookie_session']):
            raise ValidationError('Invalid cookie session')
        if not validate_fourmizzz_credentials(self.cleaned_data['server'], self.cleaned_data['username'], self.cleaned_data['password'], self.cleaned_data['cookie_session']):
            raise ValidationError('Invalid username and/or password')
        return self.cleaned_data


class AllianceTargetForm(ModelForm):
    class Meta:
        model = AllianceTarget
        fields = ('server', 'name')

    def clean(self):
        cleaned_data = super(AllianceTargetForm, self).clean()
        # TODO validate player or alliance exist
        return self.cleaned_data


class PlayerTargetForm(ModelForm):
    class Meta:
        model = PlayerTarget
        fields = ('server', 'name')

    def clean(self):
        cleaned_data = super(PlayerTargetForm, self).clean()
        # TODO validate player or alliance exist
        return self.cleaned_data
