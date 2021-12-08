# -*- coding: utf-8 -*-
import requests

from applications.allauth.socialaccount import app_settings
from applications.allauth.socialaccount.providers.oauth2.views import (
    OAuth2Adapter,
    OAuth2CallbackView,
    OAuth2LoginView,
)
from applications.allauth.compat import reverse
from applications.allauth.utils import build_absolute_uri
from django.conf import settings

from .provider import BitbucketOAuth2Provider


class BitbucketOAuth2Adapter(OAuth2Adapter):
    provider_id = BitbucketOAuth2Provider.id
    access_token_url = 'https://bitbucket.org/site/oauth2/access_token'
    authorize_url = 'https://bitbucket.org/site/oauth2/authorize'
    profile_url = 'https://api.bitbucket.org/2.0/user'
    emails_url = 'https://api.bitbucket.org/2.0/user/emails'

    def complete_login(self, request, app, token, **kwargs):
        resp = requests.get(self.profile_url, params={'access_token': token.token})
        extra_data = resp.json()
        if app_settings.QUERY_EMAIL and not extra_data.get('email'):
            extra_data['email'] = self.get_email(token)
        return self.get_provider().sociallogin_from_response(request, extra_data)

    def get_email(self, token):
        """Fetches email address from email API endpoint"""
        resp = requests.get(self.emails_url,
                            params={'access_token': token.token})
        emails = resp.json().get('values', [])
        email = ''
        try:
            email = emails[0].get('email')
            primary_emails = [e for e in emails if e.get('is_primary', False)]
            email = primary_emails[0].get('email')
        except (IndexError, TypeError, KeyError):
            return ''
        finally:
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


oauth_login = OAuth2LoginView.adapter_view(BitbucketOAuth2Adapter)
oauth_callback = OAuth2CallbackView.adapter_view(BitbucketOAuth2Adapter)
