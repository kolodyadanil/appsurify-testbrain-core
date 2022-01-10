# Generated by Django 3.2.10 on 2021-12-29 00:55

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0009_auto_20211229_0055'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('vcs', '0012_auto_20211229_0055'),
        ('testing', '0012_auto_20211208_1836'),
    ]

    operations = [
        migrations.AlterField(
            model_name='step',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='steps', to='project.project'),
        ),
        migrations.AlterField(
            model_name='test',
            name='area',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='tests', to='vcs.area'),
        ),
        migrations.AlterField(
            model_name='test',
            name='author',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='tests', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='test',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tests', to='project.project'),
        ),
        migrations.AlterField(
            model_name='testrun',
            name='author',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='test_runs', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='testrun',
            name='commit',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='test_runs', to='vcs.commit'),
        ),
        migrations.AlterField(
            model_name='testrun',
            name='project',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='test_runs', to='project.project'),
        ),
        migrations.AlterField(
            model_name='testrun',
            name='test_suite',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='test_runs', to='testing.testsuite'),
        ),
        migrations.AlterField(
            model_name='testrunresult',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='test_run_results', to='project.project'),
        ),
        migrations.AlterField(
            model_name='testrunresult',
            name='test_suite',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='test_run_results', to='testing.testsuite'),
        ),
        migrations.AlterField(
            model_name='testrunresult',
            name='test_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='test_run_results', to='testing.testtype'),
        ),
        migrations.AlterField(
            model_name='teststep',
            name='step',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='testing.step'),
        ),
        migrations.AlterField(
            model_name='teststep',
            name='test',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='testing.test'),
        ),
        migrations.AlterField(
            model_name='testsuite',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='test_suites', to='project.project'),
        ),
        migrations.AlterField(
            model_name='testsuite',
            name='test_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='test_suites', to='testing.testtype'),
        ),
        migrations.AlterField(
            model_name='testtype',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='test_types', to='project.project'),
        ),
    ]
