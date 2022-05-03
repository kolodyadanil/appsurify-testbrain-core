# -*- coding: utf-8 -*-

from django.db import migrations, transaction, models


def update_organization_type(apps, schema_editor):
    MyModel = apps.get_model('organization', 'Organization')
    MyModel.objects.filter(type='cloud').update(type='saas')
    MyModel.objects.filter(type='standalone').update(type='on-premises')


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0004_auto_20211208_1836'),
    ]

    operations = [
        migrations.RunPython(update_organization_type),
    ]
