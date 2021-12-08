# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url
from rest_framework.routers import format_suffix_patterns

from applications.api.integration.git.views import *

git_urlpatterns = [
    url(r'^repository/$', GitRepositoryCreateAPIView.as_view(), name='git-repository-create'),
    url(r'^test_connection/$', GitRepositoryTestConnection.as_view(), name='git-repository-test'),
    url(r'^hook/(?P<project_id>[0-9]+)/$', GitHookRequests.as_view(), name='git-hook'),
    url(r'^generate_hook/$', GitRepositoryGenerateHook.as_view(), name='git-repository-generate'),
    url(r'^install_hook/$', GitRepositoryInstallHook.as_view(), name='git-repository-install'),
]

urlpatterns = format_suffix_patterns(git_urlpatterns)
