# -*- coding: utf-8 -*-

from django.conf import settings
from django.contrib import admin
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),

    # path("auth/", include("rest_framework_social_oauth2.urls")),
    # path("auth/", include("applications.contrib.social_oauth2.urls")),
    # path('auth/registration/', RegistrationView.as_view()),
    # path("api/v2/customers/", include("applications.customers.urls")),

]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
