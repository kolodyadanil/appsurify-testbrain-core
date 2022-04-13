# -*- coding: utf-8 -*-
from django.conf.urls import url, include, re_path
from django.shortcuts import redirect
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
import user_agents

swagger_info = openapi.Info(
    title=str("TestBrain API"),
    default_version=str(""),
    description=str("""This is a project.
The `swagger-ui` view can be found [here](/api/cached/swagger).
The `ReDoc` view can be found [here](/api/cached/redoc).
The swagger YAML document can be found [here](/api/cached/swagger.yaml).
You can log in using the pre-existing user"""),
    terms_of_service=str(""),
    contact=openapi.Contact(email=str("")),
    license=openapi.License(name=str("License")),
)

SchemaView = get_schema_view(
    info=swagger_info,
    # schemes=['http', 'https'],
    validators=[],
    public=True,
    permission_classes=[permissions.AllowAny, ],
)


def root_redirect(request):
    user_agent_string = request.META.get('HTTP_USER_AGENT', '')
    user_agent = user_agents.parse(user_agent_string)
    if user_agent.is_mobile:
        schema_view = 'cschema-redoc'
    else:
        schema_view = 'cschema-swagger-ui'
    return redirect(schema_view, permanent=True)


# urls.py
urlpatterns = [
    url(r'^swagger(?P<format>.json|.yaml)$', SchemaView.without_ui(cache_timeout=0), name='schema-json'),
    url(r'^swagger/$', SchemaView.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    url(r'^redoc/$', SchemaView.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    url(r'^cached/swagger(?P<format>.json|.yaml)$', SchemaView.without_ui(cache_timeout=None), name='cschema-json'),
    url(r'^cached/swagger/$', SchemaView.with_ui('swagger', cache_timeout=None), name='cschema-swagger-ui'),
    url(r'^cached/redoc/$', SchemaView.with_ui('redoc', cache_timeout=None), name='cschema-redoc'),
    url(r'^$', root_redirect),

    url(r'^account/', include('applications.allauth.urls')),
    url(r'^organization/', include('applications.organization.urls')),
    url(r'^cli/', include('applications.api.cli.urls')),
    url(r'^notification/', include('applications.api.notification.urls')),
    url(r'^report/', include('applications.api.report.urls')),
    url(r'^payments/', include('applications.api.payments.urls')),

    url(r'^', include('applications.api.project.urls')),
    url(r'^', include('applications.api.testing.urls')),
    url(r'^', include('applications.api.vcs.urls')),
    url(r'^', include('applications.api.external.urls')),
    url(r'^', include('applications.api.celery.urls')),

    url(r'^', include('applications.api.integration.urls')),
    url(r'^', include('applications.api.license.urls')),
    url(r'^', include('applications.api.user_role.urls')),

]
