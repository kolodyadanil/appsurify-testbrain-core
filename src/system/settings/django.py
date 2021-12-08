# -*- coding: utf-8 -*-

from system.env import env, BASE_DIR

DEBUG = env.bool("DJANGO_DEBUG", default=True)

PLATFORM = env.str("PLATFORM", default="on-premises")

if PLATFORM == "on-premises":
    SITE_ID = 1

SECRET_KEY = env.str("DJANGO_SECRET_KEY", default="FAKE###T[*R)+Grx!%CwWXm)m+^;nFwTd,tc6Fhi/B@1Sd(XMC")

SECRET_KEYS = {
    "GITHUB": env("GITHUB_SECRET_KEY", default=SECRET_KEY),
    "LOCAL": env("LOCAL_SECRET_KEY", default=SECRET_KEY),

}

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["*", ])
BASE_SITE_DOMAIN = env.str('DJANGO_BASE_SITE_DOMAIN', default='localhost')
BASE_ORG_DOMAIN = env.str('DJANGO_BASE_ORG_DOMAIN', default='localhost')

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.sites",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

]

THIRD_PARTY_APPS = [
    "corsheaders",
    "grappelli",
    "django_celery_beat",
    "django_celery_monitor",
    "django_filters",
    "mptt",
    "rest_framework",
    "rest_framework.authtoken",
    # "rest_framework_filters",

]

LOCAL_APPS = [
    "applications.allauth",
    "applications.allauth.account",
    "applications.allauth.socialaccount",
    "applications.allauth.socialaccount.providers.github",
    "applications.allauth.socialaccount.providers.google",
    "applications.allauth.socialaccount.providers.bitbucket_oauth2",
    "applications.organization",
    "applications.project",
    "applications.vcs",
    "applications.testing",
    "applications.notification",
    "applications.integration",
    "applications.integration.github",
    "applications.integration.bitbucket",
    "applications.integration.perforce",
    "applications.integration.git",
    "applications.integration.ssh",
    "applications.integration.ssh_v2",
    "applications.integration.jira",
    "applications.api",
    # "applications.license",

]

INSTALLED_APPS = [
    *DJANGO_APPS,
    *THIRD_PARTY_APPS,
    *LOCAL_APPS
]

# MIDDLEWARE
# ------------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

]

# URLS
# ------------------------------------------------------------------------------
APPEND_SLASH = False
ROOT_URLCONF = "system.urls"

# TEMPLATES
# ------------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
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

            ],
        },
    },
]

# (W/A)SGI
# ------------------------------------------------------------------------------
WSGI_APPLICATION = "system.wsgi.application"
ASGI_APPLICATION = "system.asgi.application"

# PASSWORDS
# ------------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},

]

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# INTERNATIONALIZATION
# ------------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# DATETIME FORMAT
# ------------------------------------------------------------------------------
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DATETIME_INPUT_FORMATS = "%Y-%m-%d %H:%M:%S"

# STORAGE
# ------------------------------------------------------------------------------
STORAGE_ROOT = env.path("DJANGO_STORAGE_ROOT", default=BASE_DIR / ".." / "storage")

# STATIC
# ------------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = env.path("DJANGO_STATIC_ROOT", default=BASE_DIR / ".." / "static")

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",

]
STATICFILES_DIRS = [

]

# MEDIA
# ------------------------------------------------------------------------------
MEDIA_URL = "/media/"
MEDIA_ROOT = env.path("DJANGO_MEDIA_ROOT", default=BASE_DIR / ".." / "media")

# FIXTURES
# ------------------------------------------------------------------------------
FIXTURE_DIRS = [
    BASE_DIR / "fixtures",

]

# HTTP
# ------------------------------------------------------------------------------
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DATA_UPLOAD_MAX_NUMBER_FIELDS = 512 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 512 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 512 * 1024 * 1024
