# -*- coding: utf-8 -*-
# Generated by Django 1.11.24 on 2020-01-27 12:44
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0004_auto_20200119_1133'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='type',
            field=models.IntegerField(blank=True, choices=[(0, 'risk'), (1, 'alert'), (2, 'defect'), (3, 'test run'), (4, 'monitor'), (5, 'test_prioritization'), (6, 'risk_analysis')], default=2),
        ),
    ]
