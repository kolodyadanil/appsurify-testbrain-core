# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-08-14 21:21
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vcs', '0002_filechange_blame'),
    ]

    operations = [
        migrations.AlterField(
            model_name='filechange',
            name='status',
            field=models.IntegerField(choices=[(0, 'unknown'), (1, 'added'), (2, 'modified'), (3, 'deleted'), (4, 'renamed')], default=1),
        ),
    ]
