# Generated by Django 4.2.6 on 2023-10-28 10:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scraper', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='fourmizzzserver',
            name='n_scanned_pages',
            field=models.IntegerField(default=100, verbose_name='Number of scanned pages'),
        ),
    ]
