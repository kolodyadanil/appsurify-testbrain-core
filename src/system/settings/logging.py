# -*- coding: utf-8 -*-
from system.env import env, Path, BASE_DIR

# LOGGING
# ------------------------------------------------------------------------------
LOGS_ROOT = env.path("DJANGO_LOGS_ROOT", default=BASE_DIR / ".." / "logs")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse"
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue"
        }
    },
    "formatters": {
        "default": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s",

        },
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(filename)s:%(lineno)d %(name)s %(funcName)s %(message)s"
        }
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "default",

        },
        "common.file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_ROOT / Path("common.log"),
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 7,
            "formatter": "verbose"
        },
        "applications.file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_ROOT / Path("applications.log"),
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 7,
            "formatter": "verbose"
        },
        "flower.file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_ROOT / Path("flower.log"),
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 7,
            "formatter": "verbose"
        },
        "celery.file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_ROOT / Path("celery.log"),
            "maxBytes": 1024 * 1024 * 100,
            "backupCount": 7,
            "formatter": "verbose"
        },
        "mail": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "formatter": "default",
        },
        "null": {
            "class": "logging.NullHandler"
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", ]
    },
    "loggers": {
        "py.warnings": {
            "handlers": ["null", ],
        },
        "django": {
            "handlers": ["console", ],
            "propagate": True,
        },
        "applications": {
            "handlers": ["console", "applications.file", ],
            "level": "DEBUG",
            "propagate": False
        },
        "flower": {
            "handlers": ["console", "flower.file", ],
            "level": "DEBUG",
            "propagate": False
        },
        "celery": {
            "handlers": ["console", "celery.file", ],
            "level": "DEBUG",
            "propagate": False
        },
        "": {
            "handlers": ["console", "common.file", ],
            "level": "DEBUG",
        },
    }
}
