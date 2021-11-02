# -*- coding: utf-8 -*-

from .base import env, BASE_DIR

PLATFORM = env.str("PLATFORM", default="saas")

STORAGE_ROOT = env.path("STORAGE_ROOT", default=str(BASE_DIR.path("..").path("storage")))

# BASE_SITE_DOMAIN = env.str("BASE_SITE_DOMAIN", default="localhost")
# BASE_ORG_DOMAIN = env.str("BASE_ORG_DOMAIN", default="localhost")
#
# LICENSE_BALANCE = env.int("LICENSE_BALANCE", default=60000)
