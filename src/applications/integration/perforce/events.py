# -*- coding: utf-8 -*-

from applications.integration.perforce.models import PerforceRepository
from applications.integration.tasks import update_perforce_repository


def event_push(repository_id):
    """

    :param project_id: id project object
    :return:
    """
    repository = PerforceRepository.objects.get(id=repository_id)
    task = update_perforce_repository.delay(repository.id, on_push=True)
    return task.status
