from applications.allauth.socialaccount.providers.discord.provider import DiscordProvider
from applications.allauth.socialaccount.tests import OAuth2TestsMixin
from applications.allauth.tests import MockedResponse, TestCase


class DiscordTests(OAuth2TestsMixin, TestCase):
    provider_id = DiscordProvider.id

    def get_mocked_response(self):
        return MockedResponse(200, """{
            "id": "80351110224678912",
            "username": "Nelly",
            "discriminator": "1337",
            "avatar": "8342729096ea3675442027381ff50dfe",
            "verified": true,
            "email": "nelly@example.com"
        }""")
