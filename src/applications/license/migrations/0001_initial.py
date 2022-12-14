# -*- coding: utf-8 -*-
# Generated by Django 1.11.24 on 2021-02-20 15:51
from __future__ import unicode_literals

import applications.license.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('organization', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LicenseKey',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('default', models.BooleanField(default=False)),
                ('balance', models.IntegerField(default=0, verbose_name='time balance')),
                ('expired', models.DateTimeField(blank=True, null=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('uuid', models.UUIDField(default=uuid.uuid4, null=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='license_keys', to='organization.Organization')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='license_keys', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'license key',
                'verbose_name_plural': 'licenses keys',
            },
            managers=[
                ('objects', applications.license.models.LicenseKeyManager()),
            ],
        ),
    ]
