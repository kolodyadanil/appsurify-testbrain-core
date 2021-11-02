# -*- coding: utf-8 -*-

from .base import env, BASE_DIR

DEBUG = env.bool("DEBUG", default=True)

SECRET_KEY = env.str("SECRET_KEY", default="FAKE###T[*R)+Grx!%CwWXm)m+^;nFwTd,tc6Fhi/B@1Sd(XMC")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*", ])

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DATETIME_INPUT_FORMATS = "%Y-%m-%d %H:%M:%S"
DATA_UPLOAD_MAX_NUMBER_FIELDS = 512 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 512 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 512 * 1024 * 1024


# DATABASES
# ------------------------------------------------------------------------------
DATABASES = {"default": env.db("DATABASE_URL")}

# CACHES
# ------------------------------------------------------------------------------
CACHES = {"default": env.cache("CACHE_URL", default="locmemcache://")}


# Channels
# ------------------------------------------------------------------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env.cache("CACHE_URL", default="redis://localhost:6379/0")],
        },
    },
}

# URLS
# ------------------------------------------------------------------------------
APPEND_SLASH = True
ROOT_URLCONF = "system.urls"

# (W/A)SGI
# ------------------------------------------------------------------------------
WSGI_APPLICATION = "system.wsgi.application"
ASGI_APPLICATION = "system.asgi.application"

# APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    # "django.contrib.sites",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

]

THIRD_PARTY_APPS = [
    "corsheaders",
    # 'django_celery_monitor',
    # 'django_celery_beat',
    # 'django_filters',
    # 'mptt',
    # 'rest_framework_filters',
    # 'celery',
    # 'django_celery_beat',
    #
    # "guardian",
    # "channels",
    "rest_framework",
    # "oauth2_provider",
    # "social_django",
    # "rest_framework_social_oauth2",

]

LOCAL_APPS = [
    "applications.customers",
    # "applications.contrib.social_oauth2",

    "applications.projects",

    "applications.integrations.vcs",
    # 'applications.vcs',
    # 'applications.testing',
    # 'applications.notification',
    # 'applications.integration',
    # 'applications.integration.github',
    # 'applications.integration.bitbucket',
    # 'applications.integration.perforce',
    # 'applications.integration.git',
    # 'applications.integration.ssh',
    # 'applications.integration.ssh_v2',
    # 'applications.integration.jira',
    # 'applications.api',

]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# USER
# ------------------------------------------------------------------------------
AUTH_USER_MODEL = "customers.User"

# PASSWORDS
# ------------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},

]

# MIDDLEWARE
# ------------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "applications.customers.middlewares.OrganizationMiddleware",

]

# STATIC
# ------------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = env.path("STATIC_ROOT", default=str(BASE_DIR.path("..").path("static")))

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",

]
STATICFILES_DIRS = [

]

# MEDIA
# ------------------------------------------------------------------------------
MEDIA_URL = "/media/"
MEDIA_ROOT = env.path("MEDIA_ROOT", default=str(BASE_DIR.path("..").path("media")))

# TEMPLATES
# ------------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR("templates"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                # OAuth2
                # "social_django.context_processors.backends",
                # "social_django.context_processors.login_redirect",
            ],
        },
    },
]

# FIXTURES
# ------------------------------------------------------------------------------
FIXTURE_DIRS = [
    # BASE_DIR('fixtures'),

]

# SECURITY
# ------------------------------------------------------------------------------
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = None

# mptt
# ------------------------------------------------------------------------------
MPTT_ADMIN_LEVEL_INDENT = 20
