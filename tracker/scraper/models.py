from django.db import models
from django.utils.html import format_html

from scraper.web_agent import get_alliance_members


class FourmizzzCredentials(models.Model):
    server = models.fields.CharField(max_length=100, choices=[("s1", "s1"), ("s2", "s2"), ("s3", "s3"), ("s4", "s4")], unique=True)
    username = models.fields.CharField(max_length=100)
    cookie_session = models.fields.CharField(max_length=100, help_text=f"""Grab the value from cookie PHPSESSID ({format_html("<a target='_blank' rel='noopener' href='https://developer.chrome.com/docs/devtools/application/cookies/'>Click here</a>")})""")

    def __str__(self):
        return f'{self.username} ({self.server})'


class AllianceTarget(models.Model):
    server = models.fields.CharField(max_length=100, choices=[("s1", "s1"), ("s2", "s2"), ("s3", "s3"), ("s4", "s4")])
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('server', 'name')

    def save(self, *args, **kwargs):
        super(AllianceTarget, self).save(*args, **kwargs)

        cookie_session = FourmizzzCredentials.objects.filter(server="s1").first().cookie_session
        player_names = get_alliance_members(self.server, self.name, cookie_session)

        player_targets = []
        for player_name in player_names:
            player_target = PlayerTarget(
                alliance=self,
                server=self.server,
                name=player_name,
            )
            player_targets.append(player_target)

        PlayerTarget.objects.bulk_create(player_targets)

    def __str__(self) -> str:
        return f"{self.name} ({self.server})"


class PlayerTarget(models.Model):
    server = models.fields.CharField(max_length=100, choices=[("s1", "s1"), ("s2", "s2"), ("s3", "s3"), ("s4", "s4")])
    name = models.fields.CharField(max_length=100)
    alliance = models.ForeignKey(
        AllianceTarget,
        on_delete=models.CASCADE,  # This will delete PlayerTargets when their AllianceTarget is deleted
        null=True,  # Allow AllianceTarget to be optional
        blank=True,
        editable=False,  # Make PlayerTargets not editable by the user
    )

    class Meta:
        unique_together = ('server', 'name')

    def __str__(self) -> str:
        return f"{self.name} ({self.server})"


class PrecisionSnapshot(models.Model):
    time = models.fields.DateTimeField(auto_now_add=True)
    player = models.ForeignKey(PlayerTarget, on_delete=models.CASCADE, editable=False)
    hunting_field = models.fields.PositiveBigIntegerField(editable=False)
    trophies = models.fields.IntegerField(editable=False)
    hunting_field_diff = models.fields.BigIntegerField(editable=False, default=0)
    trophies_diff = models.fields.IntegerField(editable=False, default=0)
    processed = models.fields.BooleanField(default=False)


class RankingSnapshot(models.Model):
    time = models.fields.DateTimeField(auto_now_add=True)
    server = models.fields.CharField(max_length=100, choices=[("s1", "s1"), ("s2", "s2"), ("s3", "s3"), ("s4", "s4")], editable=False)
    player = models.fields.CharField(max_length=100, editable=False)
    hunting_field = models.fields.PositiveBigIntegerField(editable=False)
    trophies = models.fields.IntegerField(editable=False)
    hunting_field_diff = models.fields.BigIntegerField(editable=False, default=0)
    trophies_diff = models.fields.IntegerField(editable=False, default=0)


# def DiscordBot(models.Model):
#     name = models.fields.CharField(max_length=100)
