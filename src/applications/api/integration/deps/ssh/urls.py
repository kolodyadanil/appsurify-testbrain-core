# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url
from rest_framework import routers

from applications.api.integration.ssh.views import *

router = routers.DefaultRouter()

router.register(r'', GitSSHRepositoryViewSet)

urlpatterns = router.urls

urlpatterns += [
    url(r'^hook/(?P<project_id>[0-9]+)/$', GitSSHHookRequests.as_view(), name='git-ssh-hook')
]
