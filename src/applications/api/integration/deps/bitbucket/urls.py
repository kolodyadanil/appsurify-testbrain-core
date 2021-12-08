# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url
from rest_framework.routers import format_suffix_patterns

from applications.api.integration.bitbucket.views import *

bitbucket_urlpatterns = [
    url(r'^repos/$', BitbucketRepositoryCreateListAPIView.as_view(), name='bitbucket-repository-list'),
    url(r'^hook/(?P<project_id>[0-9]+)/', BitbucketHookRequests.as_view(), name='bitbucket-hook'),
    url(r'^repos/full/$', BitbucketRepositoryFullListAPIView.as_view(), name='bitbucket-repository-full-list'),
]

urlpatterns = format_suffix_patterns(bitbucket_urlpatterns)
