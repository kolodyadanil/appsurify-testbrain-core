# Generated by Django 3.2.7 on 2021-09-14 08:44

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('organization', '0003_auto_20210914_0844'),
        ('project', '0005_project_auto_area_on_commit'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='organization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='projects', to='organization.organization'),
        ),
        migrations.AlterField(
            model_name='projectowner',
            name='project',
            field=models.OneToOneField(on_delete=django.db.models.deletion.DO_NOTHING, related_name='owner', to='project.project'),
        ),
        migrations.AlterField(
            model_name='projectowner',
            name='project_user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.DO_NOTHING, to='project.projectuser'),
        ),
        migrations.AlterField(
            model_name='projectuser',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='project_users', to='project.project'),
        ),
        migrations.AlterField(
            model_name='projectuser',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='project_projectuser', to=settings.AUTH_USER_MODEL),
        ),
    ]
