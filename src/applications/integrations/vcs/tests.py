# -*- coding: utf-8 -*-
from django.test import TestCase, Client, override_settings
from django.test.client import RequestFactory
from applications.integrations.vcs.models import Repository


class RepositoryModelTestCase(TestCase):
    fixtures = ["customers", "projects", "vcs", ]

    def setUp(self) -> None:
        pass

    def test_01_load_fixtures(self):
        repository = Repository.objects.get(id=1)
        self.assertEqual(repository.path, "whenessel/appsurify-testbrain-cli")
