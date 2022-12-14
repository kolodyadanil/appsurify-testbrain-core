# -*- coding: utf-8 -*-
from applications.allauth.socialaccount.providers.auth0.provider import Auth0Provider
from applications.allauth.socialaccount.tests import OAuth2TestsMixin
from applications.allauth.tests import MockedResponse, TestCase


class Auth0Tests(OAuth2TestsMixin, TestCase):
    provider_id = Auth0Provider.id

    def get_mocked_response(self):
        return MockedResponse(200, """
            {
                "picture": "https://secure.gravatar.com/avatar/123",
                "email": "mr.bob@your.Auth0.server.example.com",
                "id": 2,
                "user_id": 2,
                "identities": [],
                "name": "Mr Bob"
            }
        """)
