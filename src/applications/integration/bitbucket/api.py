from datetime import datetime, timedelta

import requests
from django.conf import settings
from applications.allauth.socialaccount.models import SocialApp

BITBUCKET_API_URL = 'https://api.bitbucket.org/2.0'


def refresh_bitbucket_token(social_token):
    social_app = SocialApp.objects.filter(provider='bitbucket_oauth2').last()
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': social_token.token_secret,
    }

    response = requests.post('https://bitbucket.org/site/oauth2/access_token', data=data,
                             auth=(social_app.client_id, social_app.secret))
    json_response = response.json()

    if not json_response.get('access_token'):
        return None

    social_token.expires_at = datetime.now() + timedelta(seconds=json_response.get('expires_in'))
    social_token.token = json_response.get('access_token')
    social_token.token_secret = json_response.get('refresh_token')
    social_token.save()

    return json_response


def create_web_hook(repository_full_name, access_token, domain, project_id):
    try:
        repository_full_name = repository_full_name.split('/')
        repository_owner = repository_full_name[0]
        repository_name = repository_full_name[1]
    except IndexError:
        repository_owner = ''
        repository_name = repository_full_name

    url = BITBUCKET_API_URL + '/repositories/{}/{}/hooks'.format(repository_owner, repository_name)
    headers = {
        'Authorization': 'Bearer {}'.format(access_token)
    }
    payload = {
        'description': 'api hook',
        'url': '{}://{}/api/bitbucket/hook/{}/'.format(settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL, domain, project_id),
        'active': True,
        'events': [
            'repo:push',
            'repo:updated',
            'repo:commit_status_updated',
            'repo:commit_status_created',
            'repo:commit_comment_created',
            'issue:created',
            'issue:updated',
            'issue:comment_created'
        ]
    }
    response = requests.post(url=url, headers=headers, json=payload)

    return response


def delete_web_hook(repository_full_name, access_token, id_hook):
    repository_full_name = repository_full_name.split('/')
    repository_owner = repository_full_name[0]
    repository_name = repository_full_name[1]
    url = BITBUCKET_API_URL + '/repositories/{}/{}/hooks/{}'.format(repository_owner, repository_name, id_hook)
    headers = {
        'Authorization': 'Bearer {}'.format(access_token)
    }

    response = requests.delete(url=url, headers=headers)
    return response


def get_admin_repos_list(access_token):
    repos = []
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer %s' % access_token
    }
    next_url = 'https://api.bitbucket.org/2.0/repositories?role=admin&pagelen=500'

    while next_url:
        response = requests.get(next_url, headers=headers)
        result = response.json()
        next_url = result.get('next')
        repos += result.get('values', [])

    list_repos = [repo.get('full_name') for repo in repos]

    return list_repos


def get_full_list_repos(access_token):
    results = []
    repos = []
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer %s' % access_token
    }
    next_url = 'https://api.bitbucket.org/2.0/repositories?role=member&pagelen=500'

    while next_url:
        response = requests.get(next_url, headers=headers)
        result = response.json()
        next_url = result.get('next')
        repos += result.get('values', [])

    admin_repos = get_admin_repos_list(access_token=access_token)

    for repo in repos:
        full_name = repo.get('full_name')
        is_admin = True if full_name in admin_repos else False
        item = {'full_name': full_name, 'link': repo.get('links', {}).get('html', {}).get('href'), 'is_admin': is_admin}
        results.append(item)

    return results
