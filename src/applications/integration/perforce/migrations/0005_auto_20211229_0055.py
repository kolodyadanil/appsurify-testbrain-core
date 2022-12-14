# Generated by Django 3.2.10 on 2021-12-29 00:55

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0009_auto_20211229_0055'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('perforce_integration', '0004_alter_perforcerepository_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='perforcerepository',
            name='project',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='perforce_repository', to='project.project'),
        ),
        migrations.AlterField(
            model_name='perforcerepository',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='perforce_repository', to=settings.AUTH_USER_MODEL),
        ),
    ]
