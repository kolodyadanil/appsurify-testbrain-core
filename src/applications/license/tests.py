# -*- coding: utf-8 -*-

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


"""
>>> username, domain = entered_email.split('@')
>>> organization_name = ''.join([str(x).capitalize() for x in domain.split('.')])
>>> organization_slug = slugify(organization_name)
>>> User = get_user_model()
>>> user = User.objects.create_user(username=entered_email.split('@')[0], email=entered_email, password=entered_password)
>>> email = EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
>>> organization = create_organization(user, organization_name, slug=organization_slug, is_active=True, org_defaults={'site': site}, org_user_defaults={'is_admin': True})
if hasattr(settings, 'SITE_ID'):
    stat = self.SiteModel.objects.filter(id=settings.SITE_ID).update(
        domain='{}.{}'.format(organization_slug, self.base_domain),
        name='{}.{}'.format(organization_slug, self.base_domain)
    )
    site = self.SiteModel.objects.get(id=settings.SITE_ID)
else:
    site = self.SiteModel.objects.create(domain='{}.{}'.format(organization_slug, self.base_domain), name='{}.{}'.format(organization_slug, self.base_domain))


"""

LIC_DICT = {u'balance': 1000,
u'default': True,
u'expired': 'None',
u'organization': {u'name': u'Demo', u'slug': u'demo'},
u'site': {u'domain': u'demo.appsurify.local',
u'name': u'demo.appsurify.local'},
u'user': {u'email': u'whenessel@gmail.com',
u'password': u'pbkdf2_sha256$36000$XMxcpZ1Gt3vF$dOagSm32bUP3l7/d2rTJqvMEhQncBgBH8ZpLUcvJK7o=',
u'username': u'whenessel'},
u'uuid': 'e2495add-cd2f-4ec4-9efc-fb8dc8acea57'}


LIC_DICT_ENC = """eyJ1dWlkIjogImUyNDk1YWRkLWNkMmYtNGVjNC05ZWZjLWZiOGRjOGFjZWE1NyIsICJkZWZhdWx0
IjogdHJ1ZSwgInNpdGUiOiB7ImRvbWFpbiI6ICJkZW1vLmFwcHN1cmlmeS5sb2NhbCIsICJuYW1l
IjogImRlbW8uYXBwc3VyaWZ5LmxvY2FsIn0sICJ1c2VyIjogeyJ1c2VybmFtZSI6ICJ3aGVuZXNz
ZWwiLCAicGFzc3dvcmQiOiAicGJrZGYyX3NoYTI1NiQzNjAwMCRYTXhjcFoxR3QzdkYkZE9hZ1Nt
MzJiVVAzbDcvZDJyVEpxdk1FaFFuY0JnQkg4WnBMVWN2Sks3bz0iLCAiZW1haWwiOiAid2hlbmVz
c2VsQGdtYWlsLmNvbSJ9LCAib3JnYW5pemF0aW9uIjogeyJuYW1lIjogIkRlbW8iLCAic2x1ZyI6
ICJkZW1vIn0sICJiYWxhbmNlIjogMTAwMCwgImV4cGlyZWQiOiBudWxsfQ=="""


LIC_EXTRA_DICT_ENC = """eyJ1dWlkIjogImM2MTRjNDkxLWVhNWQtNDZkZC1iOGRlLWQ3NTljM2ZhYmFjMSIsICJkZWZhdWx0
IjogZmFsc2UsICJzaXRlIjogeyJkb21haW4iOiAiZGVtby5hcHBzdXJpZnkubG9jYWwiLCAibmFt
ZSI6ICJkZW1vLmFwcHN1cmlmeS5sb2NhbCJ9LCAidXNlciI6IHsidXNlcm5hbWUiOiAid2hlbmVz
c2VsIiwgInBhc3N3b3JkIjogInBia2RmMl9zaGEyNTYkMzYwMDAkWE14Y3BaMUd0M3ZGJGRPYWdT
bTMyYlVQM2w3L2QyclRKcXZNRWhRbmNCZ0JIOFpwTFVjdkpLN289IiwgImVtYWlsIjogIndoZW5l
c3NlbEBnbWFpbC5jb20ifSwgIm9yZ2FuaXphdGlvbiI6IHsibmFtZSI6ICJEZW1vIiwgInNsdWci
OiAiZGVtbyJ9LCAiYmFsYW5jZSI6IDUwMCwgImV4cGlyZWQiOiAiMjAyMS0wMy0yMiAxOTo0MDox
NiswMDowMCJ9"""


LIC_EXTRA_DICT_ENC_2 = """eyJ1dWlkIjogIjE5MDZiYTY2LTExNzAtNDI0NS04MGQ4LWQ5ZWI0MmUxYTIxZSIsICJkZWZhdWx0
IjogZmFsc2UsICJzaXRlIjogeyJkb21haW4iOiAiZGVtby5hcHBzdXJpZnkubG9jYWwiLCAibmFt
ZSI6ICJkZW1vLmFwcHN1cmlmeS5sb2NhbCJ9LCAidXNlciI6IHsidXNlcm5hbWUiOiAid2hlbmVz
c2VsIiwgInBhc3N3b3JkIjogInBia2RmMl9zaGEyNTYkMzYwMDAkWE14Y3BaMUd0M3ZGJGRPYWdT
bTMyYlVQM2w3L2QyclRKcXZNRWhRbmNCZ0JIOFpwTFVjdkpLN289IiwgImVtYWlsIjogIndoZW5l
c3NlbEBnbWFpbC5jb20ifSwgIm9yZ2FuaXphdGlvbiI6IHsibmFtZSI6ICJEZW1vIiwgInNsdWci
OiAiZGVtbyJ9LCAiYmFsYW5jZSI6IDIwMCwgImV4cGlyZWQiOiAiMjAyMS0wMy0yMiAxODoxODo0
OSswMDowMCJ9"""

class TestModel(TestCase):

    def setUp(self):
        self.entered_email = 'whenessel@appsurify.inc'
        self.entered_password = 'qwerty@123'

    def test_00_skip(self):
        self.skipTest('All time passed')

    def test_01_create_raw_lic(self):
        organization = create_organization_from_credentials(self.entered_email, self.entered_password,
                                                            create_license=True, request=None)

        lic = LicenseKey.objects._create(organization=organization,
                                         balance=settings.DEFAULT_LICENSE_BALANCE,
                                         expired=timezone.now(), default=False)

        self.assertIsInstance(lic, LicenseKey)

    def test_02_create_default_lic(self):
        organization = create_organization_from_credentials(self.entered_email, self.entered_password,
                                                            create_license=False, request=None)

        lic = LicenseKey.objects.create_default(organization=organization)

        self.assertIsInstance(lic, LicenseKey)

    def test_03_create_extra_lic(self):
        organization = create_organization_from_credentials(self.entered_email, self.entered_password,
                                                            create_license=True, request=None)

        lic = organization.license_keys.get(default=True)

        self.assertIsInstance(lic, LicenseKey)

        lic_extra = LicenseKey.objects.create_extra(
            organization=organization, balance=200, expired=timezone.now()+timezone.timedelta(weeks=4))

        self.assertIsInstance(lic_extra, LicenseKey)

        total_balance = LicenseKey.objects.filter(
            organization=organization).aggregate(total_balance=Sum('balance'))['total_balance']

        self.assertEqual(total_balance, 1200)

    def test_04_get_only_active_keys(self):
        organization = create_organization_from_credentials(self.entered_email, self.entered_password,
                                                            create_license=True, request=None)

        lic_extra_1 = LicenseKey.objects.create_extra(
            organization=organization, balance=200, expired=timezone.now() + timezone.timedelta(weeks=4))
        lic_extra_2 = LicenseKey.objects.create_extra(
            organization=organization, balance=300, expired=timezone.now() - timezone.timedelta(days=1))

        total_balance = LicenseKey.objects.filter(
            organization=organization).aggregate(total_balance=Sum('balance'))['total_balance']
        self.assertEqual(total_balance, 1500)

        total_active_balance = LicenseKey.get_available_balance(organization=organization)

        self.assertEqual(total_active_balance, 1200)

    def test_05_init_organization_from_key(self):
        organization = create_organization_from_key(LIC_DICT_ENC, request=None)
        self.assertIsNotNone(organization)

    def test_06_add_extra_key(self):
        organization = create_organization_from_key(LIC_DICT_ENC, request=None)
        self.assertIsNotNone(organization)

        lic_extra = LicenseKey.add_extra_key(organization=organization, license_key=LIC_EXTRA_DICT_ENC)
        lic_extra2 = LicenseKey.add_extra_key(organization=organization, license_key=LIC_EXTRA_DICT_ENC_2)

        balance = LicenseKey.get_available_balance(organization=organization)

        self.assertEqual(balance, 1700)

        self.assertEqual(lic_extra2.uuid, '1906ba66-1170-4245-80d8-d9eb42e1a21e')
