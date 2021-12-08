# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class PerforceConfig(AppConfig):
    name = 'applications.integration.perforce'
    label = 'perforce_integration'
    verbose_name = _('Perforce integration')
