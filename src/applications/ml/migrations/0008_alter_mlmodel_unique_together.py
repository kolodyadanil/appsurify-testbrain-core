# Generated by Django 3.2.12 on 2022-04-07 10:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('testing', '0018_auto_20220403_1514'),
        ('ml', '0007_auto_20220407_1020'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='mlmodel',
            unique_together={('test_suite', 'test')},
        ),
    ]
