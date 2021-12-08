# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url

from rest_framework import routers

from applications.api.integration.jira.views import *

router = routers.DefaultRouter()

router.register(r'credentials', JiraCredentialModelViewSet)
router.register(r'projects', JiraProjectModelViewSet)
router.register(r'issues', JiraIssueModelViewSet)

urlpatterns = router.urls
