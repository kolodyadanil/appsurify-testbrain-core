# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.auth import get_user_model
from rest_framework.exceptions import APIException

from applications.integration.git.models import GitRepository
from applications.vcs.models import Branch, Commit, Tag
from applications.integration.tasks import make_processing_workflow

User = get_user_model()


def event_tag(data, repository_id):
    repository = GitRepository.objects.get(id=repository_id)
    project = repository.project
    tagger = data.get('tagger')
    tag_name = data.get('ref')
    commit = Commit.objects.get(sha=data.get('sha'), project=project)
    tag = Tag(project=project, tag=tag_name, tagger=tagger, target_object=commit)
    tag.save()
    return 'success'


def event_commit(data, repository_id):
    repository = GitRepository.objects.get(id=repository_id)
    workflow = make_processing_workflow(project_id=repository.project_id, repository_id=repository.id,
                                        model_name=repository._meta.model_name, data=data, since_time=None)
    task = workflow.delay()
    return task.status


def event_delete(data, repository_id):
    ref_type = {
        'branch': event_delete_branch,
        'tags': event_delete_tag,
    }

    result = ref_type.get(data.get('ref_type'))(data, repository_id)

    return result


def event_delete_branch(data, repository_id):
    repository = GitRepository.objects.get(id=repository_id)
    branch = Branch.objects.get(name=data.get('ref'), project_id=repository.project_id)
    branch.delete()
    return 'success'


def event_delete_tag(data, repository_id):
    repository = GitRepository.objects.get(id=repository_id)
    tag = Tag.objects.get(tag=data.get('ref'), project_id=repository.project_id)
    tag.delete()
    return 'success'
