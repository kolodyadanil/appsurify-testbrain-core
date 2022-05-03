# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url, include
from rest_framework import routers

from .views import *

router = routers.DefaultRouter()

router.register(r'notifications', NotificationModelViewSet)

urlpatterns = router.urls
