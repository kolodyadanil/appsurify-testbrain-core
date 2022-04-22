# Generated by Django 3.2.12 on 2022-03-29 22:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('vcs', '0012_auto_20211229_0055'),
    ]

    state_operations = [
        migrations.CreateModel(
            name='CommitAreas',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created',
                 models.DateTimeField(auto_now_add=True, help_text='Auto-generated field', verbose_name='created')),
                ('updated', models.DateTimeField(auto_now=True, help_text='Auto-generated and auto-updated field',
                                                 verbose_name='updated')),
                ('area', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='vcs.area')),
                ('commit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='vcs.commit')),
            ],
            options={
                'db_table': 'vcs_commit_areas',
            },
        ),
        migrations.AlterModelTable(
            name='commitareas',
            table='vcs_commit_areas'
        ),
        migrations.AlterField(
            model_name='commit',
            name='areas',
            field=models.ManyToManyField(blank=True, related_name='commits', through='vcs.CommitAreas', to='vcs.Area'),
        ),
        migrations.CreateModel(
            name='AreaDependencies',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created',
                 models.DateTimeField(auto_now_add=True, help_text='Auto-generated field', verbose_name='created')),
                ('updated', models.DateTimeField(auto_now=True, help_text='Auto-generated and auto-updated field',
                                                 verbose_name='updated')),
                ('from_area', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='to_areas',
                                                to='vcs.area')),
                ('to_area', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='from_areas',
                                              to='vcs.area')),
            ],
            options={
                'db_table': 'vcs_area_dependencies',
            },
        ),
        migrations.AlterField(
            model_name='area',
            name='dependencies',
            field=models.ManyToManyField(blank=True, related_name='depended_on', through='vcs.AreaDependencies',
                                         to='vcs.Area'),
        ),

    ]

    operations = [
        migrations.SeparateDatabaseAndState(state_operations=state_operations),
        migrations.AddField(
            model_name='CommitAreas',
            name='created',
            field=models.DateTimeField(auto_now_add=True, help_text='Auto-generated field', verbose_name='created'),
        ),
        migrations.AddField(
            model_name='CommitAreas',
            name='updated',
            field=models.DateTimeField(auto_now=True, help_text='Auto-generated and auto-updated field',
                                       verbose_name='updated'),
        ),
        migrations.AlterModelTable(
            name='commitareas',
            table='vcs_commit_areas',
        ),
        migrations.AddField(
            model_name='AreaDependencies',
            name='created',
            field=models.DateTimeField(auto_now_add=True, help_text='Auto-generated field', verbose_name='created'),
        ),
        migrations.AddField(
            model_name='AreaDependencies',
            name='updated',
            field=models.DateTimeField(auto_now=True, help_text='Auto-generated and auto-updated field',
                                       verbose_name='updated'),
        ),
        migrations.AlterModelTable(
            name='areadependencies',
            table='vcs_area_dependencies',
        ),

    ]
