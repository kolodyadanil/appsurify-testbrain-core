# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url

from applications.organization.views import check_company_name_view


urlpatterns = [
    url(r'^check-name/$', check_company_name_view, name='organization_check_name'),
]
