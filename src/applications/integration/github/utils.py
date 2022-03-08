# -*- coding: utf-8 -*-

import requests
import tempfile
from datetime import datetime, timedelta
from dateutil import parser as datetimeparser
from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseServerError, HttpResponse
from django.utils.encoding import force_bytes
from hashlib import sha1, sha256
from hmac import HMAC, compare_digest

from applications.allauth.account.utils import user_username, user_email, user_field
from applications.allauth.utils import valid_email_or_none

from applications.vcs.models import Branch, Commit, File, FileChange, Area


def upload_github_avatar(url):
    response = requests.get(url, stream=True)
    if response.status_code != requests.codes.ok:
        return None

    temp = tempfile.NamedTemporaryFile()

    for block in response.iter_content(1024 * 8):
        if not block:
            return None

        temp.write(block)

    return temp


def verify_secret_hook(request, context):
    received_sign = request.META.get('HTTP_X_HUB_SIGNATURE_256', 'sha256=').split('sha256=')[-1].strip()
    if not received_sign:
        return False, 'Signature not found'

    data = context.get('body')

    secret = settings.SECRET_KEYS.get('GITHUB')
    expected_sign = HMAC(key=secret, msg=data, digestmod=sha256).hexdigest()

    accept_result = compare_digest(received_sign, expected_sign)
    if not accept_result:
        return False, 'Permission denied'
    return True, 'OK'


def populate_user(user, data):
    username = data.get('login')
    email = data.get('email')
    name = data.get('name')
    user_username(user, username or '')
    user_email(user, valid_email_or_none(email) or '')
    name_parts = (name or '').partition(' ')
    user_field(user, 'first_name', name_parts[0])
    user_field(user, 'last_name', name_parts[2])
    return user


def prepare_branch(branch_name):
    ref = branch_name
    if "refs/remotes/origin/" in ref:
        ref = ref[len("refs/remotes/origin/"):]
    elif "remotes/origin/" in ref:
        ref = ref[len("remotes/origin/"):]
    elif "origin/" in ref:
        ref = ref[len("origin/"):]
    elif "refs/heads/" in ref:
        ref = ref[len("refs/heads/"):]
    elif "heads/" in ref:
        ref = ref[len("heads/"):]
    return ref


def processing_commits_fast(project=None, repository=None, data=None):

    if data is None:
        return False

    if repository is None:
        return False

    if project is None:
        project = repository.project

    ref = data.get('ref', 'main')
    commits = data.get('commits', [])

    refspec = prepare_branch(ref)
    branch, _ = Branch.objects.get_or_create(project=repository.project, name=refspec)

    for commit in commits:
        sha = commit['id']
        display_id = commit['id'][:7]
        message = commit['message'][:255]
        timestamp = datetimeparser.parse(commit['timestamp'])
        author = commit['author']
        committer = commit['committer']
        url = commit['url']

        defaults = {
            'repo_id': sha,
            'display_id': display_id,
            'message': message,
            'author': author,
            'committer': committer,
            'stats': {
                'deletions': 0,
                'additions': 0,
                'total': 0
            },
            'timestamp': timestamp.strftime('%Y-%m-%dT%H:%M:%S'),
            'url': url
        }
        new_commit, created = Commit.objects.get_or_create(
            project=project,
            sha=sha,
            defaults=defaults
        )
        area_default = Area.get_default(project=project)
        area_through_model = Commit.areas.through
        area_through_model.objects.update_or_create(commit_id=new_commit.id, area_id=area_default.id)

        branch_through_model = Commit.branches.through
        branch_through_model.objects.update_or_create(commit_id=new_commit.id, branch_id=branch.id)

    return True
