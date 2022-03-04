# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class GitSSHv2Config(AppConfig):
    name = 'applications.integration.ssh_v2'
    label = 'git_ssh_v2_integration'
    verbose_name = _('Git SSH v2 integration')

    def ready(self):
        import applications.integration.ssh_v2.signals
