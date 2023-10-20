from django.contrib import admin
from django.utils.html import format_html
from engineering_notation import EngNumber

from scraper.models import FourmizzzCredentials, PlayerTarget, AllianceTarget
from scraper.forms import FourmizzzCredentialsForm, PlayerTargetForm, AllianceTargetForm

from scraper.web_agent import get_player_hunting_field_and_trophies, get_player_alliance


@admin.register(FourmizzzCredentials)
class FourmizzzCredentialsAdmin(admin.ModelAdmin):
    form = FourmizzzCredentialsForm


@admin.register(PlayerTarget)
class PlayerTargetAdmin(admin.ModelAdmin):
    form = PlayerTargetForm
    list_display = ('server', 'show_name', 'show_alliance', "hunting_field", "trophies")
    readonly_fields = ('server', 'name')
    list_filter = ('server', 'alliance')

    def show_name(self, obj):
        return format_html("<a target='_blank' rel='noopener' href='http://s1.fourmizzz.fr/Membre.php?Pseudo={name}'>{name}</a>", name=obj.name)
    show_name.short_description = "Name"

    def show_alliance(self, obj):
        credentials = FourmizzzCredentials.objects.filter(server="s1").first()
        if credentials:
            return format_html("<a target='_blank' rel='noopener' href='http://s1.fourmizzz.fr/classementAlliance.php?alliance={alliance}'>{alliance}</a>", alliance=get_player_alliance(obj.server, obj.name, credentials.cookie_session))
    show_alliance.short_description = "Alliance"

    def hunting_field(self, obj):
        # Retrieve the desired value from the FourmizzzCredentials model where server is "s1"
        credentials = FourmizzzCredentials.objects.filter(server="s1").first()
        if credentials:
            return EngNumber(get_player_hunting_field_and_trophies(obj.server, obj.name, credentials.cookie_session)[0])

    def trophies(self, obj):
        # Retrieve the desired value from the FourmizzzCredentials model where server is "s1"
        credentials = FourmizzzCredentials.objects.filter(server="s1").first()
        if credentials:
            return get_player_hunting_field_and_trophies(obj.server, obj.name, credentials.cookie_session)[1]


@admin.register(AllianceTarget)
class AllianceTargetAdmin(admin.ModelAdmin):
    form = AllianceTargetForm
    list_display = ('server', 'show_name')
    readonly_fields = ('server', 'name')
    list_filter = ('server', )

    def show_name(self, obj):
        return format_html("<a target='_blank' rel='noopener' href='http://s1.fourmizzz.fr/classementAlliance.php?alliance={name}'>{name}</a>", name=obj.name)
    show_name.short_description = "Alliance"
