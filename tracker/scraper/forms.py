from django.forms import ModelForm, PasswordInput, CharField
from django.core.exceptions import ValidationError

from scraper.models import FourmizzzCredentials
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
        if not validate_fourmizzz_cookie_session(self.cleaned_data['server'], self.cleaned_data['cookie_session']):
            raise ValidationError('Invalid cookie session')
        if not validate_fourmizzz_credentials(self.cleaned_data['server'], self.cleaned_data['username'], self.cleaned_data['password'], self.cleaned_data['cookie_session']):
            raise ValidationError('Invalid username and/or password')
        return self.cleaned_data
