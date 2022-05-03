# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class GitSSHConfig(AppConfig):
    name = 'applications.integration.ssh'
    label = 'git_ssh_integration'
    verbose_name = _('Git SSH integration')

    def ready(self):
        pass
