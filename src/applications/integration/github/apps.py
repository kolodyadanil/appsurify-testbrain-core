# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class GithubConfig(AppConfig):
    name = 'applications.integration.github'
    label = 'github_integration'
    verbose_name = _('Github integration')

