# -*- coding: utf-8 -*-

from .base import env, BASE_DIR


AUTHENTICATION_BACKENDS = [
    # "social_core.backends.github.GithubOAuth2",
    # "applications.contrib.social_oauth2.backends.DjangoOAuth2",
    "django.contrib.auth.backends.ModelBackend",

]

OAUTH2_PROVIDER = {
    # "OAUTH2_BACKEND_CLASS": "oauth2_provider.oauth2_backends.JSONOAuthLibCore",
    "SCOPES": {
        "read": "Read scope",
        "write": "Write scope",
    }
}

SOCIAL_AUTH_GITHUB_KEY = env.str("SOCIAL_AUTH_GITHUB_KEY", default="7663ca07015c1d9dcadd")
SOCIAL_AUTH_GITHUB_SECRET = env.str("SOCIAL_AUTH_GITHUB_SECRET", default="d8fe6615d19701e442ec40fab7e0136cf6cd0a6a")

SOCIAL_AUTH_PIPELINE = [
    "social_core.pipeline.social_auth.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.auth_allowed",
    "social_core.pipeline.social_auth.social_user",
    "social_core.pipeline.user.get_username",
    "social_core.pipeline.social_auth.associate_by_email",
    "social_core.pipeline.user.create_user",
    "social_core.pipeline.social_auth.associate_user",
    "social_core.pipeline.social_auth.load_extra_data",
    "social_core.pipeline.user.user_details",

]

SOCIAL_AUTH_PROTECTED_USER_FIELDS = ['email', ]
SOCIAL_AUTH_IMMUTABLE_USER_FIELDS = ['email', ]

SOCIAL_AUTH_FIELDS_STORED_IN_SESSION = ["state", "domain", ]
SOCIAL_AUTH_JSONFIELD_ENABLED = True
SOCIAL_AUTH_PASSWORDLESS = False

# SOCIAL_AUTH_REDIRECT_FIELD_NAME = "org"
# SOCIAL_AUTH_EMAIL_FORM_HTML = "email_signup.html"
# SOCIAL_AUTH_EMAIL_VALIDATION_FUNCTION = "applications.contrib.social_oauth2.mail.send_validation"
# SOCIAL_AUTH_EMAIL_VALIDATION_URL = "/email-sent/"
# SOCIAL_AUTH_USERNAME_FORM_HTML = "username_signup.html"
#
# LOGIN_URL = ""
# LOGIN_REDIRECT_URL = "/auth/done/"
# SOCIAL_AUTH_STRATEGY = "social_django.strategy.DjangoStrategy"
# SOCIAL_AUTH_STORAGE = "social_django.models.DjangoStorage"
