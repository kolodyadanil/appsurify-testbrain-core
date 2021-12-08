# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.core.exceptions import ObjectDoesNotExist

from applications.project.models import Project
from applications.vcs.models import Area
from system.celery_app import app


@app.task(bind=True)
def create_area_from_folders_task(self, project_id):
    project = Project.objects.filter(pk=project_id)
    if not project.exists():
        raise ObjectDoesNotExist()

    Area.create_from_folders(project_id)

    return True
