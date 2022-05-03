# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url, include
from rest_framework import routers

from .views import *

project_list = ProjectModelViewSet.as_view({
    'get': 'list',
    'post': 'create',
})

project_detail = ProjectModelViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'delete': 'destroy',
})

project_user_list = ProjectUserModelViewSet.as_view({
    'get': 'list',
    'post': 'create',

})

project_user_detail = ProjectUserModelViewSet.as_view({
    'delete': 'destroy'
})

project_summary = ProjectSummaryView.as_view({
    'get': 'retrieve'
})

router = routers.DefaultRouter()
router.register(r'projects', ProjectModelViewSet)

urlpatterns = router.urls

urlpatterns += [
    url(r'^projects/(?P<project_pk>[0-9]+)/users/$', project_user_list, name='project-user-list'),
    url(r'^projects/(?P<project_pk>[0-9]+)/summary/$', project_summary, name='project-summary'),
    url(r'^projects/(?P<project_pk>[0-9]+)/users/(?P<project_user_pk>[0-9]+)/$', project_user_detail,
        name='project-user-detail'),
]
