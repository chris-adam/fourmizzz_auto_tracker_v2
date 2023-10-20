from django.contrib import admin
from django.utils.html import format_html
from engineering_notation import EngNumber

from scraper.models import FourmizzzCredentials, PlayerTarget, AllianceTarget, PrecisionSnapshot
from scraper.forms import FourmizzzCredentialsForm, PlayerTargetForm, AllianceTargetForm

from scraper.web_agent import get_player_alliance


@admin.register(FourmizzzCredentials)
class FourmizzzCredentialsAdmin(admin.ModelAdmin):
    form = FourmizzzCredentialsForm


@admin.register(PlayerTarget)
class PlayerTargetAdmin(admin.ModelAdmin):
    form = PlayerTargetForm
    list_display = ('server', 'show_name', 'show_alliance', "hunting_field", "trophies")
    list_filter = ('server', 'alliance')

    def get_readonly_fields(self, request, obj=None):
        # Allow create but not edit
        return ['server', 'name'] if obj else []

    def show_name(self, obj):
        return format_html("<a target='_blank' rel='noopener' href='http://s1.fourmizzz.fr/Membre.php?Pseudo={name}'>{name}</a>", name=obj.name)
    show_name.short_description = "Name"

    def show_alliance(self, obj):
        credentials = FourmizzzCredentials.objects.filter(server=obj.server).first()
        if credentials:
            return format_html("<a target='_blank' rel='noopener' href='http://s1.fourmizzz.fr/classementAlliance.php?alliance={alliance}'>{alliance}</a>", alliance=get_player_alliance(obj.server, obj.name, credentials.cookie_session))
    show_alliance.short_description = "Alliance"

    def hunting_field(self, obj):
        return EngNumber(PrecisionSnapshot.objects.filter(player=obj).last().hunting_field)

    def trophies(self, obj):
        return PrecisionSnapshot.objects.filter(player=obj).last().trophies


@admin.register(AllianceTarget)
class AllianceTargetAdmin(admin.ModelAdmin):
    form = AllianceTargetForm
    list_display = ('server', 'show_name')
    list_filter = ('server', )

    def get_readonly_fields(self, request, obj=None):
        # Allow create but not edit
        return ['server', 'name'] if obj else []

    def show_name(self, obj):
        return format_html("<a target='_blank' rel='noopener' href='http://s1.fourmizzz.fr/classementAlliance.php?alliance={name}'>{name}</a>", name=obj.name)
    show_name.short_description = "Alliance"


@admin.register(PrecisionSnapshot)
class PrecisionSnapshotAdmin(admin.ModelAdmin):
    list_display = ('time', 'player', 'hunting_field', 'trophies')
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
