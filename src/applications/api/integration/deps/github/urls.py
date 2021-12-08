# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url
from rest_framework.routers import format_suffix_patterns

from applications.api.integration.github.views import *

github_urlpatterns = [
    url(r'^repos/$', GithubRepositoryCreateListAPIView.as_view(), name='github-repository-list'),
    url(r'^repos/full/$', GithubRepositoryFullListAPIView.as_view(), name='github-repository-full-list'),
    url(r'^repos/(?P<project_id>[0-9]+)/$', GithubRepositoryRetrieveDestroyAPIView.as_view(),
        name='github-repository-detail'),

    url(r'^hook/(?P<project_id>[0-9]+)/', GithubHookRequests.as_view(), name='github-hook'),
]

urlpatterns = format_suffix_patterns(github_urlpatterns)
