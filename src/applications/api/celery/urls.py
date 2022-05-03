# -*- coding: utf-8 -*-

from rest_framework import routers
from django.conf.urls import url

from applications.api.celery.views import TaskResultViewSet

router = routers.DefaultRouter()

# router.register(r'task-result', TaskResultViewSet.as_view({'get': 'retrieve'}))
urlpatterns = [
    url('task-result/(?P<task_id>.+)/', TaskResultViewSet.as_view({'get': 'retrieve'})),
]

urlpatterns += router.urls
