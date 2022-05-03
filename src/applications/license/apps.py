# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.utils.translation import ugettext_lazy as _
from applications.license.migrations import create_functions


class LicenseConfig(AppConfig):
    name = 'applications.license'
    label = 'license'
    verbose_name = _('License Manager')

    def ready(self):
        import signals
        post_migrate.connect(create_functions, sender=self)
