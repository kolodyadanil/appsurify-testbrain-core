# -*- coding: utf-8 -*-

from django.test import TestCase
from django.contrib.sites.models import Site
from django.contrib.auth import get_user_model

from applications.organization.utils import *
from applications.project.models import *
from applications.testing.models import *
from applications.vcs.models import *
from django.test import TestCase

from django.db.models import Count, Sum
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.sites.models import Site
from django.contrib.auth import get_user_model
from django.template.defaultfilters import slugify
from django.utils import timezone
from applications.organization.utils import (
    create_organization,
    get_current_organization,
    create_organization_from_credentials,
    create_organization_from_key
)
from applications.license.models import LicenseKey


User = get_user_model()

LIC_DICT_ENC = """eyJ1dWlkIjogImUyNDk1YWRkLWNkMmYtNGVjNC05ZWZjLWZiOGRjOGFjZWE1NyIsICJkZWZhdWx0
IjogdHJ1ZSwgInNpdGUiOiB7ImRvbWFpbiI6ICJkZW1vLmFwcHN1cmlmeS5sb2NhbCIsICJuYW1l
IjogImRlbW8uYXBwc3VyaWZ5LmxvY2FsIn0sICJ1c2VyIjogeyJ1c2VybmFtZSI6ICJ3aGVuZXNz
ZWwiLCAicGFzc3dvcmQiOiAicGJrZGYyX3NoYTI1NiQzNjAwMCRYTXhjcFoxR3QzdkYkZE9hZ1Nt
MzJiVVAzbDcvZDJyVEpxdk1FaFFuY0JnQkg4WnBMVWN2Sks3bz0iLCAiZW1haWwiOiAid2hlbmVz
c2VsQGdtYWlsLmNvbSJ9LCAib3JnYW5pemF0aW9uIjogeyJuYW1lIjogIkRlbW8iLCAic2x1ZyI6
ICJkZW1vIn0sICJiYWxhbmNlIjogMTAwMCwgImV4cGlyZWQiOiBudWxsfQ=="""


class TestAreaModel(TestCase):

    def setUp(self):
        self.organization = create_organization_from_key(LIC_DICT_ENC, request=None)
        self.project = Project.o

    def test_00_skip(self):
        self.skipTest('All time passed')

    def test_01_check_organization(self):
        self.assertIsNotNone(get_current_organization(request=None))

    def test_02_add_area_to_file(self):
        filename_1 = 'src/java/file/Payments/Payments.java'
        filename_2 = 'src/java/file/Payments/Payment2.java'
        filename_3 = 'src/java/file/Payments/ACHPayments/ACHPayments.java'

