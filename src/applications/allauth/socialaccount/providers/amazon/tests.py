from applications.allauth.socialaccount.tests import OAuth2TestsMixin
from applications.allauth.tests import MockedResponse, TestCase

from .provider import AmazonProvider


class AmazonTests(OAuth2TestsMixin, TestCase):
    provider_id = AmazonProvider.id

    def get_mocked_response(self):
        return MockedResponse(200, """
        {
          "Profile":{
                        "CustomerId":"amzn1.account.K2LI23KL2LK2",
                        "Name":"John Doe",
                        "PrimaryEmail":"johndoe@example.com"
                    }
        }""")
