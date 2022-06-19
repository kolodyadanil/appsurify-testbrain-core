# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.core.exceptions import ObjectDoesNotExist

from applications.project.models import Project
from applications.vcs.models import Area
from celery import shared_task


@shared_task
def create_area_from_folders_task():
    projects = Project.objects.all()
    ids = list()
    for project in projects:
        Area.create_from_folders(project.id)
        ids.append(project.id)
    return f'Area is auto generated for projects {ids}'
