# Generated by Django 3.2.10 on 2021-12-29 00:15

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0005_20211214_1041'),
        ('project', '0007_auto_20211208_1836'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='organization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='projects', to='organization.organization'),
        ),
    ]
