# Generated by Django 3.2.12 on 2022-03-21 22:25

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0009_auto_20211229_0055'),
        ('testing', '0014_auto_20220310_1158'),
    ]

    operations = [
        migrations.AlterField(
            model_name='testtype',
            name='rerun_all',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='testtype',
            name='rerun_flaky',
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name='TestReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('test_run_name', models.CharField(blank=True, max_length=255)),
                ('commit_sha', models.CharField(max_length=255)),
                ('name', models.CharField(blank=True, max_length=255)),
                ('source', models.TextField()),
                ('destination', models.TextField(blank=True)),
                ('format', models.CharField(choices=[('UNKNOWN', 'UNKNOWN'), ('NUNIT3', 'NUNIT3'), ('JUNIT', 'JUNIT'), ('TRX', 'TRX')], default='UNKNOWN', max_length=128, verbose_name='format')),
                ('status', models.CharField(choices=[('PENDING', 'PENDING'), ('PROCESSING', 'PROCESSING'), ('SUCCESS', 'SUCCESS'), ('FAILURE', 'FAILURE'), ('UNKNOWN', 'UNKNOWN')], default='UNKNOWN', max_length=128, verbose_name='status')),
                ('created', models.DateTimeField(auto_now_add=True, help_text='Auto-generated field', verbose_name='created')),
                ('updated', models.DateTimeField(auto_now=True, help_text='Auto-generated and auto-updated field', verbose_name='updated')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='test_reports', to='project.project')),
                ('test_suite', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='test_reports', to='testing.testsuite')),
            ],
            options={
                'verbose_name': 'test report',
                'verbose_name_plural': 'test reports',
                'ordering': ['id', 'project'],
            },
        ),
    ]
