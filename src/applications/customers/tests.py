# -*- coding: utf-8 -*-
from django.test import TestCase, Client, override_settings
from django.test.client import RequestFactory
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.exceptions import ValidationError
from applications.customers.models import User, Organization
from applications.customers.exceptions import OrganizationOwnershipRequired
from applications.customers.shortcuts import get_current_organization
from applications.customers.middlewares import OrganizationMiddleware


class UserModelTestCase(TestCase):
    fixtures = ["customers", ]

    def setUp(self) -> None:
        pass

    def test_01_load_fixtures(self):
        user = User.objects.get(email="admin@localhost.localdomain")
        self.assertEqual(user.email, "admin@localhost.localdomain")

    def test_02_auth_user_model(self):
        user_model = get_user_model()
        self.assertEqual(user_model._meta.label, settings.AUTH_USER_MODEL)

    def test_03_create_user(self):
        super_user = User.objects.create_superuser(email="super@localhost.localdomain", password="TestP@ssw0RD")
        self.assertEqual(super_user.email, "super@localhost.localdomain")
        new_user = User.objects.create_user(email="new@localhost.localdomain", password="TestP@ssw0RD")
        self.assertEqual(new_user.email, "new@localhost.localdomain")

    def test_04_create_user_validation(self):
        with self.assertRaises(ValidationError):
            user = User.objects.create_user(email="someemail", password="TestP@ssw0RD")
        # with self.assertRaises(ValidationError):
        #     user = User.objects.create_user(email="mailbox@localhost.localdomain", password="")
        user = User.objects.create_user(email="mailbox@localhost.localdomain", password="TestP@ssw0RD")
        self.assertEqual(user.email, "mailbox@localhost.localdomain")
        self.assertEqual(user.check_password("TestP@ssw0RD"), True)
        self.assertEqual(user.check_password("TestP@ssw0RD2"), False)


class OrganizationModelTestCase(TestCase):
    fixtures = ["customers", ]

    def setUp(self) -> None:
        self.factory = RequestFactory()

    def test_01_load_fixtures(self):
        organization = Organization.objects.get(name="Appsurify INC")
        self.assertEqual(organization.domain, "appsurify-inc")
        self.assertEqual(organization.platform_display, "SaaS")
        self.assertEqual(organization.platform, "saas")

    def test_02_add_organization_users(self):
        admin = User.objects.get(email="admin@localhost.localdomain")
        user = User.objects.get(email="user@localhost.localdomain")

        organization = Organization.objects.get(name="Appsurify INC")
        organization.add_user(user=admin)
        self.assertEqual(organization.is_admin(user=admin), True)
        self.assertEqual(organization.is_owner(user=admin), True)

        organization.add_user(user=user)
        self.assertEqual(organization.is_admin(user=user), False)
        self.assertEqual(organization.is_owner(user=user), False)

    def test_03_remove_organization_users(self):
        admin = User.objects.get(email="admin@localhost.localdomain")
        user = User.objects.get(email="user@localhost.localdomain")

        organization = Organization.objects.get(name="Appsurify INC")
        organization.add_user(user=admin)
        organization.add_user(user=user)

        self.assertEqual(organization.users_count, 2)

        organization.remove_user(user=user)
        self.assertEqual(organization.users_count, 1)

        with self.assertRaises(OrganizationOwnershipRequired):
            organization.remove_user(user=admin)

    @override_settings(PLATFORM="on-premises")
    def test_04_utils_for_premises(self):
        Organization.objects.clear_cache()

        request = self.factory.get("/auth/", HTTP_HOST="appsurify-inc.appsurify.com")
        OrganizationMiddleware().process_request(request)

        organization = get_current_organization(request=request)
        self.assertIsNotNone(organization)
        self.assertEqual(organization.name, "Appsurify INC")

        request = self.factory.get("/auth/", HTTP_HOST="localhost:8000")
        OrganizationMiddleware().process_request(request)

        organization = get_current_organization(request=request)
        self.assertIsNotNone(organization)
        self.assertEqual(organization.name, "Appsurify INC")

    @override_settings(PLATFORM="saas")
    def test_05_utils_for_saas(self):
        Organization.objects.clear_cache()

        request = self.factory.get("/auth/", HTTP_HOST="appsurify-inc.appsurify.com")
        OrganizationMiddleware().process_request(request)
        organization = get_current_organization(request=request)
        self.assertIsNotNone(organization)
        self.assertEqual(organization.name, "Appsurify INC")

        request = self.factory.get("/auth/", HTTP_HOST="localhost:8000")
        OrganizationMiddleware().process_request(request)

        organization = get_current_organization(request=request)
        self.assertIsNone(organization)
