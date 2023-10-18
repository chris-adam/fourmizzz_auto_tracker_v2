from django.db import models


class FourmizzzCredentials(models.Model):
    server = models.fields.CharField(max_length=100, choices=[("s1", "s1"), ("s2", "s2"), ("s3", "s3"), ("s4", "s4")])
    username = models.fields.CharField(max_length=100)
    password = models.fields.CharField(max_length=100)
    cookie_session = models.fields.CharField(max_length=100)
    def __str__(self):
        return f'{self.username} ({self.server})'


def AllianceTarget(models.Model):
    name = models.fields.CharField(max_length=100)


def PlayerTarget(models.Model):
    name = models.fields.CharField(max_length=100)
