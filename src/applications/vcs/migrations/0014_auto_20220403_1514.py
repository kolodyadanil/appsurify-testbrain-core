# Generated by Django 3.2.12 on 2022-04-03 15:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vcs', '0013_auto_20220329_2248'),
    ]

    operations = [
        migrations.AlterField(
            model_name='areadependencies',
            name='updated',
            field=models.DateTimeField(auto_now_add=True, help_text='Auto-generated and auto-updated field', verbose_name='updated'),
        ),
        migrations.AlterField(
            model_name='commitareas',
            name='updated',
            field=models.DateTimeField(auto_now_add=True, help_text='Auto-generated and auto-updated field', verbose_name='updated'),
        ),
    ]
