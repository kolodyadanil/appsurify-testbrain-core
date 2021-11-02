# -*- coding: utf-8 -*-

from .base import env, BASE_DIR

CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_CREDENTIALS = True
CORS_PREFLIGHT_MAX_AGE = 7200
CORS_ORIGIN_WHITELIST = ["*", ]
CORS_ALLOWED_ORIGINS = [
    "http://*",
    "https://*",

]

CORS_ALLOW_METHODS = [
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",

]

CORS_ALLOW_HEADERS = [
    "x-requested-with",
    "content-type",
    "accept",
    "origin",
    "authorization",
    "x-csrftoken",

]
