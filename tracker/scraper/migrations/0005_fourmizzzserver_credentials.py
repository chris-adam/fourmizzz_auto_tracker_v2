from django.db import migrations
from django.db import models


def cookie_session_to_jar(apps, schema_editor):
    """Carry the hand-pasted PHPSESSID over into the managed cookie jar."""
    FourmizzzServer = apps.get_model("scraper", "FourmizzzServer")
    for server in FourmizzzServer.objects.exclude(cookie_session=""):
        server.cookies = {"PHPSESSID": server.cookie_session}
        server.save(update_fields=["cookies"])


def jar_to_cookie_session(apps, schema_editor):
    FourmizzzServer = apps.get_model("scraper", "FourmizzzServer")
    for server in FourmizzzServer.objects.all():
        server.cookie_session = (server.cookies or {}).get("PHPSESSID", "")
        server.save(update_fields=["cookie_session"])


class Migration(migrations.Migration):

    dependencies = [
        ("scraper", "0004_playertarget_mv"),
    ]

    operations = [
        migrations.AddField(
            model_name="fourmizzzserver",
            name="password",
            field=models.CharField(
                blank=True,
                default="",
                help_text="The password of that Fourmizzz account. Used to log back in when the game session expires.",
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name="fourmizzzserver",
            name="cookies",
            field=models.JSONField(
                default=dict,
                editable=False,
                help_text="Cookie jar managed by the tracker. Do not edit by hand.",
            ),
        ),
        migrations.AddField(
            model_name="fourmizzzserver",
            name="last_login_attempt",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="fourmizzzserver",
            name="username",
            field=models.CharField(
                help_text="Your Fourmizzz account name, used to log in to the game.",
                max_length=100,
            ),
        ),
        # Give cookie_session a default before dropping it. Reversing a RemoveField re-adds the
        # column using this definition, and it runs before the data is copied back, so without a
        # default the rollback would fail on NOT NULL for every existing row.
        migrations.AlterField(
            model_name="fourmizzzserver",
            name="cookie_session",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.RunPython(cookie_session_to_jar, jar_to_cookie_session),
        migrations.RemoveField(
            model_name="fourmizzzserver",
            name="cookie_session",
        ),
    ]
