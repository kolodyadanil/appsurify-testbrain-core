# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rest_framework import routers

from .views import *

router = routers.DefaultRouter()

router.register(r'projects', ProjectReportModelViewSet)
router.register(r'areas', AreaReportModelViewSet)
router.register(r'files', FileReportModelViewSet)
router.register(r'test-types', TestTypeReportModelViewSet)
router.register(r'test-suites', TestSuiteReportModelViewSet)
router.register(r'test-runs', TestRunReportModelViewSet)
router.register(r'test-run-results', TestRunResultReportModelViewSet)
router.register(r'tests', TestReportModelViewSet)
router.register(r'defects', DefectReportModelViewSet)
router.register(r'analysis', AnalysisViewSet)

urlpatterns = router.urls

# urlpatterns += [
#     url(r'^(?P<todo_id>\d+)/yetanother/(?P<yetanother_id>\d+)/$',
#         views.NestedTodoView.as_view(), ),
# ]
