# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class JiraConfig(AppConfig):
    name = 'applications.integration.jira'
    label = 'jira_integration'
    verbose_name = _('Jira integration')

    def ready(self):
        import applications.integration.jira.signals
