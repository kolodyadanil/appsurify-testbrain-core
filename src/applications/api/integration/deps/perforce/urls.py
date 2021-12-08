# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url
from rest_framework.routers import format_suffix_patterns

from applications.api.integration.perforce.views import *

git_urlpatterns = [
    url(r'^repository/$', PerforceRepositoryCreateAPIView.as_view(), name='perforce-repository-create'),
    url(r'^hook/(?P<project_id>[0-9]+)/$', PerforceHookRequests.as_view(), name='git-ssh-hook')
]

urlpatterns = format_suffix_patterns(git_urlpatterns)
