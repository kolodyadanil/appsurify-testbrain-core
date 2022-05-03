# -*- coding: utf-8 -*-
from django.conf.urls import url, include
from rest_framework import routers
from .views import *

router = routers.DefaultRouter()

# router.register(r'licenses', LicenseModelViewSet)

urlpatterns = [
    url("licenses/", DashboardDummyAPIView.as_view()),
    url("licenses/information-dashboard-table", DashboardDummyAPIView.as_view()),
    url("licenses/get_customer_stripe/", DashboardDummyAPIView.as_view()),

]
