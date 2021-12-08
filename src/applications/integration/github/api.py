# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

import requests
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from .models import GithubRepository, GithubIssue

GITHUB_API_URL = 'https://api.github.com'


def get_full_list_repos(access_token):
    from github import Github
    g = Github(access_token)
    repos = [{
        'full_name': repo.full_name,
        'link': repo.html_url,
        'is_admin': repo.permissions.admin
    } for repo in g.get_user().get_repos()]
    return repos


def create_web_hook(repository_full_name, access_token, domain, project_id):
    try:
        repository_full_name = repository_full_name.split('/')
        repository_owner = repository_full_name[0]
        repository_name = repository_full_name[1]
    except IndexError:
        repository_owner = ''
        repository_name = repository_full_name

    url = GITHUB_API_URL + '/repos/{}/{}/hooks'.format(repository_owner, repository_name)

    headers = {
        'Authorization': 'token {}'.format(access_token)
    }

    payload = {
        'name': 'web',
        'active': True,
        'events': [
            'push',
            'issues',
            'create',
            'delete',
            'release',
        ],
        'config': {
            'url': '{}://{}/api/github/hook/{}/'.format(settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL, domain, project_id),
            'content_type': 'json',
            'secret': settings.SECRET_KEYS.get('GITHUB'),
        }
    }
    response = requests.post(url=url, headers=headers, data=json.dumps(payload))

    return response


def delete_web_hook(repository_full_name, access_token, id_hook):
    repository_full_name = repository_full_name.split('/')
    repository_owner = repository_full_name[0]
    repository_name = repository_full_name[1]
    url = GITHUB_API_URL + '/repos/{}/{}/hooks/{}'.format(repository_owner, repository_name, id_hook)
    headers = {
        'Authorization': 'token {}'.format(access_token)
    }

    response = requests.delete(url=url, headers=headers)
    return response


def get_list_web_hook(repository_full_name, access_token):
    repository_full_name = repository_full_name.split('/')
    repository_owner = repository_full_name[0]
    repository_name = repository_full_name[1]
    url = GITHUB_API_URL + '/repos/{}/{}/hooks'.format(repository_owner, repository_name)
    headers = {
        'Authorization': 'token {}'.format(access_token)
    }

    response = requests.get(url=url, headers=headers)
    return response


def get_single_hook(repository_full_name, access_token, id_hook):
    repository_full_name = repository_full_name.split('/')
    repository_owner = repository_full_name[0]
    repository_name = repository_full_name[1]
    url = GITHUB_API_URL + '/repos/{}/{}/hooks/{}'.format(repository_owner, repository_name, id_hook)
    headers = {
        'Authorization': 'token {}'.format(access_token)
    }

    response = requests.get(url=url, headers=headers)
    return response


def edit_hook(repository_full_name, access_token, id_hook):
    repository_full_name = repository_full_name.split('/')
    repository_owner = repository_full_name[0]
    repository_name = repository_full_name[1]
    url = GITHUB_API_URL + '/repos/{}/{}/hooks/{}'.format(repository_owner, repository_name, id_hook)
    headers = {
        'Authorization': 'token {}'.format(access_token)
    }
    payload = {
        'action': True,
    }

    response = requests.patch(url=url, headers=headers, data=json.dumps(payload))
    return response


def edit_issue(defect):
    try:
        repository = GithubRepository.objects.get(project_id=defect.project_id)
    except GithubRepository.DoesNotExist:
        return False

    try:
        issue_number = GithubIssue.objects.get(defect=defect).issue_number
    except GithubIssue.DoesNotExist:
        return False

    repository_full_name = repository.github_repository_name.split('/')
    repository_owner = repository_full_name[0]
    repository_name = repository_full_name[1]

    if defect.status == defect.STATUS_CLOSED:
        state = 'closed'
    else:
        state = 'open'

    access_token = repository.token

    url = GITHUB_API_URL + '/repos/{}/{}/issues/{}'.format(repository_owner, repository_name, issue_number)
    headers = {
        'Authorization': 'token {}'.format(access_token)
    }

    payload = {
        'title': defect.name,
        'body': defect.error,
        'state': state
    }
    requests.patch(url=url, headers=headers, data=json.dumps(payload))
    return True


def get_single_commit(repository_full_name, access_token, sha):
    repository_full_name = repository_full_name.split('/')
    repository_owner = repository_full_name[0]
    repository_name = repository_full_name[1]

    url = GITHUB_API_URL + '/repos/{}/{}/commits/{}'.format(repository_owner, repository_name, sha)

    headers = {
        'Authorization': 'token {}'.format(access_token)
    }
    response = requests.get(url=url, headers=headers)

    return response


def get_branch(repository_full_name, access_token, branch):
    repository_full_name = repository_full_name.split('/')
    repository_owner = repository_full_name[0]
    repository_name = repository_full_name[1]

    url = GITHUB_API_URL + '/repos/{}/{}/branches/{}'.format(repository_owner, repository_name, branch)

    headers = {
        'Authorization': 'token {}'.format(access_token)
    }

    response = requests.get(url=url, headers=headers)

    return response


def get_ref_tags(repository_full_name, access_token, tag_name):
    repository_full_name = repository_full_name.split('/')
    repository_owner = repository_full_name[0]
    repository_name = repository_full_name[1]

    url = GITHUB_API_URL + '/repos/{}/{}/git/refs/tags/{}'.format(repository_owner, repository_name, tag_name)

    headers = {
        'Authorization': 'token {}'.format(access_token)
    }

    response = requests.get(url=url, headers=headers)

    return response


def get_commit(repository_full_name, access_token, commit_sha):
    repository_full_name = repository_full_name.split('/')
    repository_owner = repository_full_name[0]
    repository_name = repository_full_name[1]

    url = GITHUB_API_URL + '/repos/{}/{}/git/commits/{}'.format(repository_owner, repository_name, commit_sha)

    headers = {
        'Authorization': 'token {}'.format(access_token)
    }

    response = requests.get(url=url, headers=headers)

    return response


def get_tag(repository_full_name, access_token, tag_sha):
    repository_full_name = repository_full_name.split('/')
    repository_owner = repository_full_name[0]
    repository_name = repository_full_name[1]

    url = GITHUB_API_URL + '/repos/{}/{}/git/tags/{}'.format(repository_owner, repository_name, tag_sha)

    headers = {
        'Authorization': 'token {}'.format(access_token)
    }

    response = requests.get(url=url, headers=headers)

    return response


def get_content_file(url, access_token):
    headers = {
        'Authorization': 'token {}'.format(access_token)
    }

    response = requests.get(url=url, headers=headers)

    if response.status_code != 200:
        return False

    response = response.json()
    download_url = response.get('download_url')

    response_file = requests.get(url=download_url, headers=headers)

    if response_file.status_code != 200:
        return False

    return response_file.raw


def get_single_user(username, access_token):
    url = GITHUB_API_URL + '/users/{}'.format(username)
    headers = {
        'Authorization': 'token {}'.format(access_token)
    }

    response = requests.get(url=url, headers=headers)

    return response


def get_user(access_token):
    url = GITHUB_API_URL + '/user'
    headers = {
        'Authorization': 'token {}'.format(access_token)
    }

    response = requests.get(url=url, headers=headers)

    return response


def get_list_commits(repository_full_name, access_token, page=None, sha=None):
    repository_full_name = repository_full_name.split('/')
    repository_owner = repository_full_name[0]
    repository_name = repository_full_name[1]
    url = GITHUB_API_URL + '/repos/{}/{}/commits'.format(repository_owner, repository_name)
    headers = {
        'Authorization': 'token {}'.format(access_token)
    }

    parameters = {}
    if page:
        parameters.update({'page': page})
    if sha:
        parameters.update({'sha': sha})

    response = requests.get(url=url, headers=headers, params=parameters)

    return response


def get_list_branches(repository_full_name, access_token, page=None):
    repository_full_name = repository_full_name.split('/')
    repository_owner = repository_full_name[0]
    repository_name = repository_full_name[1]
    url = GITHUB_API_URL + '/repos/{}/{}/branches'.format(repository_owner, repository_name)
    headers = {
        'Authorization': 'token {}'.format(access_token)
    }

    parameters = {}
    if page:
        parameters.update({'page': page})

    response = requests.get(url=url, headers=headers, params=parameters)

    return response


def get_trees(repository_full_name, access_token, branch):
    repository_full_name = repository_full_name.split('/')
    repository_owner = repository_full_name[0]
    repository_name = repository_full_name[1]
    url = GITHUB_API_URL + '/repos/{}/{}/git/trees/{}?recursive=1'.format(repository_owner, repository_name, branch)
    headers = {
        'Authorization': 'token {}'.format(access_token)
    }

    response = requests.get(url=url, headers=headers)

    return response


def run_query(query, access_token):
    headers = {
        'Authorization': 'token {}'.format(access_token)
    }

    response = requests.post('https://api.github.com/graphql', json={'query': query}, headers=headers)

    if response.status_code == 200:
        return True, response.json()
    else:
        return False, response.json()
