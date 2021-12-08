# -*- coding: utf-8 -*-
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _
from git import GitCommandError
from rest_framework import status
from rest_framework.response import Response
import re
from applications.allauth.account.utils import user_username, user_field
from applications.allauth.socialaccount.models import SocialAccount, SocialToken
from applications.integration.bitbucket.models import BitbucketRepository, BitbucketIssue, ref_pattern
from applications.integration.tasks import make_processing_workflow
from applications.testing.models import Defect

User = get_user_model()
DEFAULT_TOKEN = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'


def event_push(data, repository_id):
    """

    :param data: data get from bitbucket webhook
    :param project_id: id project object
    :return:
    """
    repository = BitbucketRepository.objects.get(id=repository_id)
    workflow = make_processing_workflow(project_id=repository.project_id, repository_id=repository.id,
                                        model_name=repository._meta.model_name, data=data, since_time=None)
    task = workflow.delay()
    return task.status


def event_issue(data, repository_id):
    """

    :param data: data get from bitbucket webhook
    :param project_id: id project object
    :return:
    """
    action = {
        'new': event_issue_new,
        'resolved': event_issue_resolved,
        'closed': event_issue_resolved,
        'open': event_issue_open,
    }

    issue = data.get('issue')
    state = issue.get('state')

    action_function = action.get(state)

    if action_function:
        return action_function(data, repository_id)

    return False


def event_issue_new(data, repository_id):
    """

    :param data: data get from bitbucket webhook
    :param project_id: id project object
    :return:
    """
    repository = BitbucketRepository.objects.get(id=repository_id)

    project = repository.project

    name = data.get('issue').get('title')
    defect = Defect.objects.filter(name=name)

    if defect:
        return False

    reason = 'Create by Bitbucket'
    error = data.get('issue').get('content', {}).get('raw')

    found_date = data.get('issue').get('created_on')
    number = data.get('issue').get('id')

    access_token = repository.get_or_refresh_token()

    if not access_token:
        return False

    user_data = data.get('actor')

    try:
        sender = User.objects.get(socialaccount__uid=user_data.get('username'))
    except User.DoesNotExist:
        login = repository.bitbucket_repository_name.split('/')[0]

        try:
            app = repository.user.socialaccount_set.filter(provider='bitbucket_oauth2',
                                                           extra_data__username=login).first().socialtoken_set.first().app
        except Exception as e:
            return False

        social_account = SocialAccount(uid=user_data.get('username'),
                                       extra_data=user_data,
                                       provider='bitbucket_oauth2')

        user = get_user_model()()
        user.set_unusable_password()
        user_username(user, user_data.get('username') or '')
        name_parts = (user_data.get('display_name') or '').partition(' ')
        user_field(user, 'first_name', name_parts[0])
        user_field(user, 'last_name', name_parts[2])

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

    BitbucketIssue.objects.create(
        defect=defect,
        issue_number=number
    )

    return True


def event_issue_resolved(data, repository_id):
    """

    :param data: data get from bitbucket webhook
    :param project_id: id project object
    :return:
    """
    name = data.get('issue').get('title')

    try:
        defect = Defect.objects.get(name=name)
    except Defect.DoesNotExist:
        return False

    defect.status = Defect.STATUS_CLOSED
    defect.save()

    return True


def event_issue_open(data, repository_id):
    """

    :param data: data get from bitbucket webhook
    :param project_id: id project object
    :return:
    """
    name = data.get('issue').get('title')

    try:
        defect = Defect.objects.get(name=name)
    except Defect.DoesNotExist:
        return False

    defect.status = Defect.STATUS_NEW
    defect.reopen_date = data.get('issue').get('updated_on')
    defect.name = data.get('issue').get('title')
    defect.error = data.get('issue').get('content', {}).get('raw')
    defect.save()

    return True
