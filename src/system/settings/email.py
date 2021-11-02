# -*- coding: utf-8 -*-

from .base import env, BASE_DIR

EMAIL_CONFIG = env.email("EMAIL_URL", default="consolemail://")

DEFAULT_FROM_EMAIL = f"TestBrain Support Team <{EMAIL_CONFIG['EMAIL_HOST_USER']}>"

vars().update(EMAIL_CONFIG)
vars().update(EMAIL_CONFIG.get("OPTIONS", {}))
