# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.utils.translation import ugettext_lazy as _
from applications.testing.utils.db_create_functions import create_functions


class TestingConfig(AppConfig):
    name = 'applications.testing'
    verbose_name = _('Testing')
    
    # def ready(self):
    #     import signals
    #     post_migrate.connect(create_functions, sender=self)
