# -*- coding: utf-8 -*-
from __future__ import absolute_import

import re
from django.contrib.auth import get_user_model

from applications.allauth.socialaccount.models import SocialAccount, SocialToken
from applications.integration.github.api import get_commit, get_ref_tags, get_tag, get_single_user
from applications.integration.github.models import GithubRepository, GithubIssue, ref_pattern
from applications.integration.github.utils import populate_user
from applications.testing.models import Defect
from applications.vcs.models import Branch, Commit, Tag

from applications.integration.tasks import make_processing_workflow, processing_commits_fast_task



User = get_user_model()

DEFAULT_TOKEN = '0' * 40


def event_push(data, repository_id):
    repository = GithubRepository.objects.get(id=repository_id)
    workflow = make_processing_workflow(project_id=repository.project_id, repository_id=repository.id,
                                        model_name=repository._meta.model_name, data=data, since_time=None)
    task = workflow.delay()
    return task.status


def event_create(data, repository_id):
    ref_type_map = {
        'branch': event_create_branch,
        'tag': event_create_tag,
    }

    ref_type = ref_type_map.get(data.get('ref_type'))
    result = ref_type(data, repository_id)
    return result


def event_create_branch(data, repository_id):
    repository = GithubRepository.objects.get(id=repository_id)
    branch_name = data.get('ref')
    if branch_name:
        branch_name = re.sub(ref_pattern, "", branch_name)
        Branch.objects.get_or_create(name=branch_name, project_id=repository.project_id)

    return 'successful'


def event_create_tag(data, repository_id):
    repository = GithubRepository.objects.get(id=repository_id)
    project = repository.project
    access_token = repository.token

    if not access_token:
        raise ValueError('Some error with access_token')

    try:
        sender = User.objects.get(socialaccount__uid=data.get('sender').get('id'))
    except User.DoesNotExist:
        user_data = get_single_user(data.get('sender').get('login'), access_token)

        if not user_data.status_code == 200:
            raise ValueError('Fetch user info error')

        login = repository.github_repository_name.split('/')[0]
        app = repository.user.socialaccount_set.filter(provider='github',
                                                       extra_data__login=login).first().socialtoken_set.first().app

        user_data = user_data.json()
        social_account = SocialAccount(uid=user_data.get('id'), extra_data=user_data, provider='github')

        user = get_user_model()()
        user.set_unusable_password()
        populate_user(user, user_data)
        user.save()

        social_account.user_id = user.id
        social_account.save()
        social_token = SocialToken(app=app, token=DEFAULT_TOKEN, account=social_account)
        social_token.save()
        sender = user

        project.add_user(sender)

    tagger = dict(username=sender.username, email=sender.email)

    tag_name = data.get('ref')
    ref_tag = get_ref_tags(repository.github_repository_name, access_token, tag_name)
    if ref_tag.status_code == 200:
        ref_tag = ref_tag.json()
    else:
        raise ValueError('Fetch tag info error')

    message = ''
    sha_commit = ''
    if ref_tag.get('object').get('type') == 'tag':
        tag = get_tag(repository.github_repository_name, access_token, tag_sha=ref_tag.get('object').get('sha'))
        if tag.status_code == 200:
            tag = tag.json()
        else:
            raise ValueError('Fetch tag info error')

        message = tag.get('description')
        sha_commit = tag.get('object').get('sha')

    elif ref_tag.get('object').get('type') == 'commit':
        commit = get_commit(repository.github_repository_name, access_token, commit_sha=ref_tag.get('object').get('sha'))
        if commit.status_code == 200:
            commit = commit.json()

        message = commit.get('message')
        sha_commit = commit.get('sha')

    commit = Commit.objects.get(sha=sha_commit, project=project)

    repo_full_name = repository.github_repository_name.split('/')
    url = 'https://github.com/{}/{}/releases/tag/{}'.format(repo_full_name[0], repo_full_name[1], tag_name)
    tag = Tag(
        project=project,
        tag=tag_name,
        url=url,
        sender=sender,
        tagger=tagger,
        message=message,
        target_object=commit
    )

    tag.save()

    return 'success'


def event_delete(data, repository_id):
    ref_type = {
        'branch': event_delete_branch,
        'tag': event_delete_tag,
    }

    result = ref_type.get(data.get('ref_type'))(data, repository_id)
    return result


def event_delete_branch(data, repository_id):
    repository = GithubRepository.objects.get(id=repository_id)
    branch = Branch.objects.get(name=data.get('ref'), project_id=repository.project_id)
    branch.delete()
    return 'successful'


def event_delete_tag(data, repository_id):
    repository = GithubRepository.objects.get(id=repository_id)
    tag = Tag.objects.get(tag=data.get('ref'), project_id=repository.project_id)
    tag.delete()
    return 'successful'


def event_issue(data, repository_id):
    action = {
        'opened': event_issue_opened,
        'closed': event_issue_closed,
        'reopened': event_issue_reopened,
        'edited': event_issue_edited,
    }

    result = action.get(data.get('action'))(data, repository_id)

    return result


def event_issue_opened(data, repository_id):
    repository = GithubRepository.objects.get(id=repository_id)
    project = repository.project
    name = data.get('issue').get('title')
    defect = Defect.objects.filter(name=name)
    if defect:
        return False

    reason = 'Create by Github'
    error = data.get('issue').get('body')

    found_date = data.get('issue').get('created_at')
    number = data.get('issue').get('number')

    access_token = repository.token
    if not access_token:
        return False

    try:
        sender = User.objects.get(socialaccount__uid=data.get('sender').get('id'))
    except User.DoesNotExist:
        user_data = get_single_user(data.get('sender').get('login'), access_token)
        if not user_data.status_code == 200:
            return False
        login = repository.github_repository_name.split('/')[0]
        try:
            app = repository.user.socialaccount_set.filter(provider='github',
                                                           extra_data__login=login).first().socialtoken_set.first().app
        except Exception as e:
            return False

        user_data = user_data.json()
        social_account = SocialAccount(uid=user_data.get('id'),
                                       extra_data=user_data,
                                       provider='github')

        user = get_user_model()()
        user.set_unusable_password()
        populate_user(user, user_data)
        user.save()

        social_account.user_id = user.id
        social_account.save()
        social_token = SocialToken(app=app,
                                   token=DEFAULT_TOKEN,
                                   account=social_account)
        social_token.save()
        sender = user

        project.add_user(sender)

    defect = Defect.objects.create(
        project=project,
        reason=reason,
        name=name,
        error=error,
        create_type=Defect.CREATE_TYPE_AUTOMATIC,
        found_date=found_date,
        owner=sender
    )

    GithubIssue.objects.create(
        defect=defect,
        issue_number=number
    )

    return True


def event_issue_closed(data, repository_id):
    name = data.get('issue').get('title')

    try:
        defect = Defect.objects.get(name=name)
    except Defect.DoesNotExist:
        return False

    defect.status = Defect.STATUS_CLOSED
    defect.save()

    return True


def event_issue_reopened(data, repository_id):
    name = data.get('issue').get('title')

    try:
        defect = Defect.objects.get(name=name)
    except Defect.DoesNotExist:
        return False

    defect.status = Defect.STATUS_NEW
    defect.reopen_date = data.get('issue').get('updated_at')
    defect.save()

    return True


def event_issue_edited(data, repository_id):
    changes = data.get('changes')

    if changes.get('title'):
        name = changes.get('title').get('from')
    else:
        name = data.get('issue').get('title')

    try:
        defect = Defect.objects.get(name=name)
    except Defect.DoesNotExist:
        return False
    if changes.get('title') and defect.name != data.get('issue').get('title'):
        defect.name = data.get('issue').get('title')
        defect.save()
    if changes.get('body') and defect.error != data.get('issue').get('body'):
        defect.error = data.get('issue').get('body')
        defect.save()

    return True
