# -*- coding: utf-8 -*-
from applications.allauth.socialaccount.providers.gitlab.provider import GitLabProvider
from applications.allauth.socialaccount.providers.oauth2.urls import default_urlpatterns


urlpatterns = default_urlpatterns(GitLabProvider)
