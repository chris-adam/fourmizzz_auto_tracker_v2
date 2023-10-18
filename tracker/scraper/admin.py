from django.contrib import admin

from scraper.models import FourmizzzCredentials
from scraper.forms import FourmizzzCredentialsForm


class FourmizzzCredentialsAdmin(admin.ModelAdmin):
    form = FourmizzzCredentialsForm

admin.site.register(FourmizzzCredentials, FourmizzzCredentialsAdmin)
