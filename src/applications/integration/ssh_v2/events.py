# -*- coding: utf-8 -*-

import traceback
from django.contrib.auth import get_user_model

from applications.integration.ssh_v2.models import GitSSHv2Repository
from applications.integration.ssh_v2.tasks import fetch_commits_task_v2
from applications.integration.tasks import processing_commits_fast_task
from applications.vcs.models import Branch, Commit, Tag

User = get_user_model()


def event_install(data, repository_id):
    repository = GitSSHv2Repository.objects.get(id=repository_id)
    repository.is_installed_hook = True
    repository.save()
    return 'success'


def event_tag(data, repository_id):
    repository = GitSSHv2Repository.objects.get(id=repository_id)

    project = repository.project
    tagger = data.get('tagger')
    tag_name = data.get('ref')

    commit = Commit.objects.get(sha=data.get('sha'), project=project)

    tag = Tag(
        project=project,
        tag=tag_name,
        tagger=tagger,
        target_object=commit
    )
    tag.save()
    return 'success'


def event_commit(data, repository_id):
    repository = GitSSHv2Repository.objects.get(id=repository_id)
    try:
        repository.processing_commits_fast(project=repository.project, repository=repository, data=data)
        # processing_commits_fast_task(
        #     project_id=repository.project_id,
        #     repository_id=repository.id,
        #     model_name=repository._meta.model_name,
        #     data=data
        # )
    except Exception:
        print(traceback.format_exc())
    task = fetch_commits_task_v2.delay(project_id=repository.project_id,
                                       repository_id=repository.id, model_name=repository._meta.model_name, data=data)
    return task.status


def event_delete(data, repository_id):
    ref_type = {
        'branch': event_delete_branch,
        'tags': event_delete_tag,
    }

    result = ref_type.get(data.get('ref_type'))(data, repository_id)

    return result


def event_delete_branch(data, repository_id):
    repository = GitSSHv2Repository.objects.get(id=repository_id)
    branch = Branch.objects.get(name=data.get('ref'), project_id=repository.project_id)
    branch.delete()
    return 'success'


def event_delete_tag(data, repository_id):
    repository = GitSSHv2Repository.objects.get(id=repository_id)
    tag = Tag.objects.get(tag=data.get('ref'), project_id=repository.project_id)
    tag.delete()
    return 'success'
