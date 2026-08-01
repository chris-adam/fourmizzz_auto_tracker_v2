from django.core.exceptions import ValidationError
from django.forms import CharField
from django.forms import ModelForm
from django.forms import PasswordInput

from scraper.models import AllianceTarget
from scraper.models import FourmizzzServer
from scraper.models import PlayerTarget
from scraper.web_agent import LoginFailed
from scraper.web_agent import LoginRefused
from scraper.web_agent import LoginUnreachable
from scraper.web_agent import SessionExpired
from scraper.web_agent import get_alliance_members
from scraper.web_agent import login_and_validate
from scraper.web_agent import player_exists


class FourmizzzServerForm(ModelForm):
    password = CharField(
        widget=PasswordInput(render_value=False),
        required=False,
        help_text="The password of that Fourmizzz account. Leave blank to keep the current one.",
    )
    phpsessid = CharField(
        widget=PasswordInput(render_value=False),
        required=False,
        label="PHPSESSID override",
        help_text="Optional. Paste a PHPSESSID to use that session instead of logging in. "
        "Leave blank in normal use: the tracker manages its session itself.",
    )

    def __init__(self, *args, **kwargs):
        super(FourmizzzServerForm, self).__init__(*args, **kwargs)
        instance = getattr(self, "instance", None)
        if instance and instance.pk:
            self.fields["name"].widget.attrs["readonly"] = True

    def clean_name(self):
        instance = getattr(self, "instance", None)
        if instance and instance.pk:
            return instance.name
        else:
            return self.cleaned_data["name"]

    def clean_password(self):
        # A blank password on an edit means "keep what is stored", not "clear it".
        password = self.cleaned_data.get("password")
        if not password and self.instance and self.instance.pk:
            return self.instance.password
        return password

    class Meta:
        model = FourmizzzServer
        fields = ("name", "username", "password", "n_scanned_pages")

    def clean(self):
        cleaned_data = super(FourmizzzServerForm, self).clean()
        if self.errors:
            return cleaned_data

        # Build a throwaway server carrying the submitted values, so the credentials are checked
        # against the game before anything is written.
        candidate = FourmizzzServer(
            name=cleaned_data["name"],
            username=cleaned_data["username"],
            password=cleaned_data["password"],
            cookies=dict(self.instance.cookies or {}) if self.instance else {},
        )
        phpsessid = cleaned_data.get("phpsessid")
        if phpsessid:
            candidate.cookies["PHPSESSID"] = phpsessid

        if not candidate.password:
            raise ValidationError(
                "A password is required, so the tracker can log back in when the game session expires."
            )

        try:
            self.validated_cookies = login_and_validate(candidate)
        except LoginUnreachable as e:
            raise ValidationError(
                f"Could not reach Fourmizzz to check these credentials: {e}. "
                f"The game may be busy or down; try saving again."
            )
        except (LoginRefused, LoginFailed, SessionExpired) as e:
            raise ValidationError(
                f"Fourmizzz would not log us in: {getattr(e, 'reason', '') or e}. "
                f"Check the username and password."
            )
        except Exception as e:
            raise ValidationError(f"Could not reach Fourmizzz to check these credentials: {e}")

        return cleaned_data

    def save(self, commit=True):
        server = super(FourmizzzServerForm, self).save(commit=False)
        # Store the jar obtained while validating, so the tracker starts out logged in.
        server.cookies = getattr(self, "validated_cookies", server.cookies)
        if commit:
            server.save()
        return server


class AllianceTargetForm(ModelForm):
    class Meta:
        model = AllianceTarget
        fields = ("server", "name")

    def clean(self):
        cleaned_data = super(AllianceTargetForm, self).clean()
        if self.errors:
            return cleaned_data
        if not get_alliance_members(cleaned_data["server"], cleaned_data["name"]):
            raise ValidationError(
                f'Alliance {cleaned_data["name"]} not found in server {cleaned_data["server"]}'
            )
        return self.cleaned_data


class PlayerTargetForm(ModelForm):
    class Meta:
        model = PlayerTarget
        fields = ("server", "name")

    def clean(self):
        cleaned_data = super(PlayerTargetForm, self).clean()
        if self.errors:
            return cleaned_data
        if not player_exists(cleaned_data["server"], cleaned_data["name"]):
            raise ValidationError(
                f'Player {cleaned_data["name"]} not found in server {cleaned_data["server"]}'
            )
        return self.cleaned_data
