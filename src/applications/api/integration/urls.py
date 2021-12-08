# -*- coding: utf-8 -*-
from django.conf.urls import url, include
from rest_framework import routers


router = routers.DefaultRouter()

# from .views import repository_view, repository_full_view, hook_receiver_view
from . import views

router.register(r'(?P<type>(github|bitbucket|perforce|git|ssh|ssh_v2))/repository',
                views.RepositoryViewSet, basename='repository')

router.register(r'(?P<type>(github|bitbucket|perforce|git|ssh|ssh_v2))/hook',
                views.RepositoryHookViewSet, basename='hook')

# urls.py
urlpatterns = [
    url(r'^jira/', include('applications.api.integration.jira.urls')),

] + router.urls
