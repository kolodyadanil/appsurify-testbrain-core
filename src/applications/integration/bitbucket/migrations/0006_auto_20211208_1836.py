# Generated by Django 3.2.10 on 2021-12-08 18:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bitbucket_integration', '0005_auto_20210914_0844'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bitbuckethook',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='bitbucketissue',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='bitbucketrepository',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]
