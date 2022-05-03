# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from applications.allauth.socialaccount.tests import OAuthTestsMixin
from applications.allauth.tests import TestCase

from .provider import TrelloProvider


class TrelloTests(OAuthTestsMixin, TestCase):
    provider_id = TrelloProvider.id
