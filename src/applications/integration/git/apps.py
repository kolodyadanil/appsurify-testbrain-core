# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class GitConfig(AppConfig):
    name = 'applications.integration.git'
    label = 'git_integration'
    verbose_name = _('Git integration')

