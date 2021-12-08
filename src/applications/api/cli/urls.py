# -*- coding: utf-8 -*-
from django.conf.urls import url, include
from rest_framework import routers
from .views import *

router = routers.DefaultRouter()

urlpatterns = [
    url('token/server/', ServerTokenViewSet.as_view({'get': 'validate', 'post': 'validate'})),
    url('token/user/', UserTokenViewSet.as_view({'get': 'validate', 'post': 'validate'})),
    url('token/api/', APITokenViewSet.as_view({'get': 'validate', 'post': 'validate'})),
    url('organization/', OrganizationViewSet.as_view({'post': 'create', 'get': 'current'})),

    url('license/init/', LicenseViewSet.as_view({'post': 'init'})),
    url('license/add/', LicenseViewSet.as_view({'post': 'add'})),

]

urlpatterns += router.urls
