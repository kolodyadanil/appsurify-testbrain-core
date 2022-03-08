# -*- coding: utf-8 -*-
from django.apps import AppConfig
from django.db.models.signals import post_migrate
from applications.testing.utils.db_create_functions import create_functions


class TestingConfig(AppConfig):
    name = "applications.testing"
    verbose_name = "Testing"
    
    def ready(self):
        import applications.testing.signals
        # post_migrate.connect(create_functions, sender=self)
