# Generated by Django 3.2.10 on 2021-12-29 00:55

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0009_auto_20211229_0055'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('vcs', '0011_auto_20211208_1836'),
    ]

    operations = [
        migrations.AlterField(
            model_name='area',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='areas', to='project.project'),
        ),
        migrations.AlterField(
            model_name='branch',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='branches', to='project.project'),
        ),
        migrations.AlterField(
            model_name='commit',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='commits', to='project.project'),
        ),
        migrations.AlterField(
            model_name='commit',
            name='sender',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='commits', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='file',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='project.project'),
        ),
        migrations.AlterField(
            model_name='filechange',
            name='commit',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='vcs.commit'),
        ),
        migrations.AlterField(
            model_name='filechange',
            name='file',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='vcs.file'),
        ),
        migrations.AlterField(
            model_name='parentcommit',
            name='from_commit',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='from_commits', to='vcs.commit'),
        ),
        migrations.AlterField(
            model_name='parentcommit',
            name='to_commit',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='to_commits', to='vcs.commit'),
        ),
        migrations.AlterField(
            model_name='tag',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tags', to='project.project'),
        ),
        migrations.AlterField(
            model_name='tag',
            name='sender',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='tags', to=settings.AUTH_USER_MODEL),
        ),
    ]
