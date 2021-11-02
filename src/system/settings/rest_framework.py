# -*- coding: utf-8 -*-

from .base import env, BASE_DIR


REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        # "applications.api.common.filter_backends.MultiFilterClassBackend",
        # "applications.api.common.filter_backends.SearchMultiFilterClass",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # "rest_framework.authentication.TokenAuthentication",
        # "rest_framework.authentication.SessionAuthentication",
        # "oauth2_provider.contrib.rest_framework.OAuth2Authentication",
        # "applications.contrib.social_oauth2.authentication.SocialAuthentication",

    ),
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",  # "applications.api.common.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 20
}
