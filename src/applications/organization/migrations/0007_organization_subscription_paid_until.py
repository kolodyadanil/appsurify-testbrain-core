# Generated by Django 3.2.12 on 2022-04-14 19:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0006_auto_20211229_0055'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='subscription_paid_until',
            field=models.IntegerField(blank=True, default=None, null=True),
        ),
    ]
