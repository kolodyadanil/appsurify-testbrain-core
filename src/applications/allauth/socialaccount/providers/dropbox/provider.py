from applications.allauth.socialaccount import providers
from applications.allauth.socialaccount.providers.base import ProviderAccount
from applications.allauth.socialaccount.providers.oauth2.provider import OAuth2Provider


class DropboxOAuth2Account(ProviderAccount):
    pass


class DropboxOAuth2Provider(OAuth2Provider):
    id = 'dropbox'
    name = 'Dropbox'
    account_class = DropboxOAuth2Account

    def extract_uid(self, data):
        return data['account_id']

    def extract_common_fields(self, data):
        return dict(name=data['name']['display_name'],
                    email=data['email'])


providers.registry.register(DropboxOAuth2Provider)
