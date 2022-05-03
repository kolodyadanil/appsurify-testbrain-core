# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rest_framework import routers

from .views import *

router = routers.DefaultRouter()

router.register(r'external', ExternalAPIViewSet)

urlpatterns = router.urls
