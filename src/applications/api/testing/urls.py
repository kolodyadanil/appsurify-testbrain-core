# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url, include
from rest_framework import routers

from .views import *

router = routers.DefaultRouter()

router.register(r'test-types', TestTypeModelViewSet)
router.register(r'test-suites', TestSuiteModelViewSet)
router.register(r'test-runs', TestRunModelViewSet)
router.register(r'tests', TestModelViewSet)
router.register(r'steps', StepModelViewSet)
router.register(r'test-run-results', TestRunResultModelViewSet)
router.register(r'defects', DefectModelViewSet)

urlpatterns = router.urls

# urlpatterns += [
#     url(r'^(?P<todo_id>\d+)/yetanother/(?P<yetanother_id>\d+)/$',
#         views.NestedTodoView.as_view(), ),
# ]
