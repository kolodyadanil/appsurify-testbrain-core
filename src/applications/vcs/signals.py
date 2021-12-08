# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db.models import Count
from django.db.models.signals import pre_save, post_save, m2m_changed
from django.dispatch import receiver

from .models import *


@receiver(post_save, sender=File)
def model_file_default_area(sender, instance, created, **kwargs):
    file = instance
    if not file.areas.exists():
        area = Area.get_default(project=file.project)
        file.areas.add(area)
        file.save()


@receiver(m2m_changed, sender=File.areas.through)
def model_file_area_change(sender, instance, reverse, model, pk_set, action, **kwargs):
    if reverse:
        area = instance
        default_area = Area.get_default(project=area.project)
        if area != default_area:
            if action == 'pre_add':
                default_area.files.remove(*pk_set)
            if action == 'post_add':
                for commit in Commit.objects.filter(files__in=pk_set):
                    commit.sync_areas()

            if action == 'pre_remove':
                fileset = File.objects.filter(id__in=pk_set).annotate(areas__count=Count('areas')).filter(
                    areas__count=1)
                default_area.files.add(*fileset)

            if action == 'post_remove':
                for commit in Commit.objects.filter(files__in=pk_set):
                    commit.sync_areas()
