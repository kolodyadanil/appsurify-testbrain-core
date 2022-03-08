# -*- coding: utf-8 -*-
from django.conf.urls import url, include
from django.conf.urls.static import static, serve
from django.contrib import admin
from django.conf import settings
from django.http import HttpResponse
import re

urlpatterns = [
    url(r'^grappelli/', include('grappelli.urls')),  # grappelli URLS
    url(r'^admin/', admin.site.urls),
    url(r'^api/', include('applications.api.urls')),
    # url(r'^payments/', include('djstripe.urls', namespace='djstripe')),
    url(r'^healthy/', lambda r: HttpResponse(status=200, content='OK')),

]

# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

urlpatterns += [
    url(r'^%s(?P<path>.*)$' % re.escape(settings.MEDIA_URL.lstrip('/')), serve, kwargs=dict(document_root=settings.MEDIA_ROOT)),
    url(r'^%s(?P<path>.*)$' % re.escape(settings.STATIC_URL.lstrip('/')), serve, kwargs=dict(document_root=settings.STATIC_ROOT)),
]


