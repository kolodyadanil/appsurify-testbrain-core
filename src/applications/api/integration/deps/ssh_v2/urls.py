# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url
from rest_framework.routers import format_suffix_patterns

from applications.api.integration.ssh_v2.views import *


git_ssh_v2_urlpatterns = [
    url(r'^repository/$', GitSSHv2RepositoryCreateAPIView.as_view(), name='git-ssh-v2-repository-create'),
    url(r'^repository/(?P<pk>[0-9]+)/$', GitSSHv2RepositoryRetrieveAPIView.as_view(), name='git-ssh-v2-repository-retrieve'),
    # url(r'^test_connection/$', GitRepositoryTestConnection.as_view(), name='git-repository-test'),
    url(r'^hook/(?P<project_id>[0-9]+)/$', GitSSHv2HookRequests.as_view(), name='git-ssh-v2-hook'),
    url(r'^generate_hook/(?P<project_id>[0-9]+)/$', GitSSHv2RepositoryGenerateHook.as_view(), name='git-ssh-v2-repository-generate'),
    # url(r'^install_hook/(?P<project_id>[0-9]+)/$', GitSSHv2RepositoryInstallHook.as_view(), name='git-ssh-v2-repository-install'),
]


urlpatterns = format_suffix_patterns(git_ssh_v2_urlpatterns)
