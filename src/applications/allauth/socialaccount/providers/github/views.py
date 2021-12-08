# -*- coding: utf-8 -*-
import requests

from django.conf import settings
from applications.allauth.socialaccount import app_settings
from applications.allauth.socialaccount.providers.github.provider import GitHubProvider
from applications.allauth.compat import reverse
from applications.allauth.utils import build_absolute_uri
from applications.allauth.socialaccount.providers.oauth2.views import (
    OAuth2Adapter,
    OAuth2CallbackView,
    OAuth2LoginView,
)


class GitHubOAuth2Adapter(OAuth2Adapter):
    provider_id = GitHubProvider.id
    settings = app_settings.PROVIDERS.get(provider_id, {})

    if 'GITHUB_URL' in settings:
        web_url = settings.get('GITHUB_URL').rstrip('/')
        api_url = '{0}/api/v3'.format(web_url)
    else:
        web_url = 'https://github.com'
        api_url = 'https://api.github.com'

    access_token_url = '{0}/login/oauth/access_token'.format(web_url)
    authorize_url = '{0}/login/oauth/authorize'.format(web_url)
    profile_url = '{0}/user'.format(api_url)
    emails_url = '{0}/user/emails'.format(api_url)

    def complete_login(self, request, app, token, **kwargs):
        params = {'access_token': token.token}
        headers = {'Authorization': 'token {}'.format(token.token)}
        resp = requests.get(self.profile_url, params=params, headers=headers)
        extra_data = resp.json()
        if app_settings.QUERY_EMAIL and not extra_data.get('email'):
            extra_data['email'] = self.get_email(token)
        social_login = self.get_provider().sociallogin_from_response(request, extra_data)
        return social_login

    def get_email(self, token):
        email = None
        params = {'access_token': token.token}
        headers = {'Authorization': 'token {}'.format(token.token)}
        resp = requests.get(self.emails_url, params=params, headers=headers)
        emails = resp.json()
        if resp.status_code == 200 and emails:
            email = emails[0]
            primary_emails = [
                e for e in emails
                if not isinstance(e, dict) or e.get('primary')
            ]
            if primary_emails:
                email = primary_emails[0]
            if isinstance(email, dict):
                email = email.get('email', '')
        return email

    def get_callback_url(self, request, app):
        base_domain = settings.BASE_SITE_DOMAIN
        current_host = request.META.get('HTTP_HOST')
        request.META['HTTP_HOST'] = base_domain
        request.META['HTTP_X_FORWARDED_HOST'] = base_domain
        callback_url = reverse(self.provider_id + "_callback")
        protocol = self.redirect_uri_protocol
        callback = build_absolute_uri(request, callback_url, protocol) + '?host=%s' % current_host
        return callback


oauth2_login = OAuth2LoginView.adapter_view(GitHubOAuth2Adapter)
oauth2_callback = OAuth2CallbackView.adapter_view(GitHubOAuth2Adapter)
