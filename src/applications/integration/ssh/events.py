# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _
from git import GitCommandError
from rest_framework import status
from rest_framework.response import Response

from applications.integration.ssh.models import GitSSHRepository
from applications.integration.tasks import fetch_commits_task


def event_push(data, repository_id):
    """

    :param project_id: id project object
    :return:
    """
    repository = GitSSHRepository.objects.get(id=repository_id)
    task = fetch_commits_task.delay(project_id=repository.project_id, repository_id=repository.id,
                                    model_name=repository._meta.model_name, data=data, on_push=True)
    return task.status
