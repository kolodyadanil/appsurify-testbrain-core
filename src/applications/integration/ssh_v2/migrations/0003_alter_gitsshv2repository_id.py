# Generated by Django 3.2.10 on 2021-12-08 18:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('git_ssh_v2_integration', '0002_auto_20210914_0844'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gitsshv2repository',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]
