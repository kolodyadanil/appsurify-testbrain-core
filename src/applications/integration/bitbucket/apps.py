# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class BitbucketConfig(AppConfig):
    name = 'applications.integration.bitbucket'
    label = 'bitbucket_integration'
    verbose_name = _('Bitbucket integration')

