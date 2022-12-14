# Generated by Django 3.2.10 on 2021-12-08 18:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0007_auto_20211208_1836'),
        ('git_ssh_integration', '0003_alter_gitsshrepository_project'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gitsshrepository',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='gitsshrepository',
            name='project',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='git_ssh_repository', to='project.project'),
        ),
    ]
