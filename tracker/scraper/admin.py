from django.contrib import admin
from django.utils.html import format_html
from django_admin_listfilter_dropdown.filters import DropdownFilter, ChoiceDropdownFilter
from engineering_notation import EngNumber
from django_celery_results.admin import TaskResult, GroupResult
from django_celery_beat.models import (
    IntervalSchedule,
    CrontabSchedule,
    SolarSchedule,
    ClockedSchedule,
    PeriodicTask,
)

from scraper.models import FourmizzzCredentials, PlayerTarget, AllianceTarget, PrecisionSnapshot, RankingSnapshot
from scraper.forms import FourmizzzCredentialsForm, PlayerTargetForm, AllianceTargetForm

from scraper.web_agent import get_player_alliance


@admin.register(FourmizzzCredentials)
class FourmizzzCredentialsAdmin(admin.ModelAdmin):
    form = FourmizzzCredentialsForm


@admin.register(PlayerTarget)
class PlayerTargetAdmin(admin.ModelAdmin):
    form = PlayerTargetForm
    list_display = ('server', 'show_name', 'show_alliance', "hunting_field", "trophies")
    list_filter = (('server', ChoiceDropdownFilter), 'alliance')

    def get_readonly_fields(self, request, obj=None):
        # Allow create but not edit
        return ['server', 'name'] if obj else []

    def show_name(self, obj):
        return format_html("<a target='_blank' rel='noopener' href='http://s1.fourmizzz.fr/Membre.php?Pseudo={name}'>{name}</a>", name=obj.name)
    show_name.short_description = "Name"

    def show_alliance(self, obj):
        if obj.alliance:
            return format_html("<a target='_blank' rel='noopener' href='http://s1.fourmizzz.fr/classementAlliance.php?alliance={alliance}'>{alliance}</a>", alliance=obj.alliance.name)

        credentials = FourmizzzCredentials.objects.filter(server=obj.server).first()
        if not credentials:
            return

        player_alliance = get_player_alliance(obj.server, obj.name, credentials.cookie_session)
        if not player_alliance:
            return
        return format_html("<a target='_blank' rel='noopener' href='http://s1.fourmizzz.fr/classementAlliance.php?alliance={alliance}'>{alliance}</a>", alliance=player_alliance)
    show_alliance.short_description = "Alliance"

    def hunting_field(self, obj):
        last_snapshot = PrecisionSnapshot.objects.filter(player=obj).last()
        if not last_snapshot:
            return None
        return EngNumber(last_snapshot.hunting_field)

    def trophies(self, obj):
        last_snapshot = PrecisionSnapshot.objects.filter(player=obj).last()
        if not last_snapshot:
            return None
        return last_snapshot.trophies


@admin.register(AllianceTarget)
class AllianceTargetAdmin(admin.ModelAdmin):
    form = AllianceTargetForm
    list_display = ('server', 'show_name')
    list_filter = (('server', ChoiceDropdownFilter), )

    def get_readonly_fields(self, request, obj=None):
        # Allow create but not edit
        return ['server', 'name'] if obj else []

    def show_name(self, obj):
        return format_html("<a target='_blank' rel='noopener' href='http://s1.fourmizzz.fr/classementAlliance.php?alliance={name}'>{name}</a>", name=obj.name)
    show_name.short_description = "Alliance"


@admin.register(PrecisionSnapshot)
class PrecisionSnapshotAdmin(admin.ModelAdmin):
    list_display = ('pk', 'time', 'player', 'hunting_field', 'trophies', 'hunting_field_diff', 'trophies_diff', 'processed')
    list_filter = ('processed', )
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(RankingSnapshot)
class RankingSnapshotAdmin(admin.ModelAdmin):
    list_display = ('pk', 'time', 'server', 'show_player', 'show_hunting_field', 'trophies', 'hunting_field_diff', 'trophies_diff')
    list_filter = (('server', ChoiceDropdownFilter), ('player', DropdownFilter))

    def show_player(self, obj):
        return format_html("<a target='_blank' rel='noopener' href='http://s1.fourmizzz.fr/Membre.php?Pseudo={player}'>{player}</a>", player=obj.player)
    show_player.short_description = "Player"

    def show_hunting_field(self, obj):
        return EngNumber(obj.hunting_field)
    show_hunting_field.short_description = "Hunting Field"

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


# Disable Celery results admin
admin.site.unregister(TaskResult)
admin.site.unregister(GroupResult)
# Disable Celery beat admin
admin.site.unregister(SolarSchedule)
admin.site.unregister(ClockedSchedule)
admin.site.unregister(PeriodicTask)
admin.site.unregister(IntervalSchedule)
admin.site.unregister(CrontabSchedule)
