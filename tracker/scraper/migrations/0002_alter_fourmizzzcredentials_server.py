# Generated by Django 4.2.6 on 2023-10-18 20:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scraper', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fourmizzzcredentials',
            name='server',
            field=models.CharField(choices=[('s1', 's1'), ('s2', 's2'), ('s3', 's3'), ('s4', 's4')], max_length=100),
        ),
    ]
