# -*- coding: utf-8 -*-

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class GithubConfig(AppConfig):
    name = 'applications.integration.github'
    label = 'github_integration'
    verbose_name = _('Github integration')

    def ready(self):
        import applications.integration.github.signals
