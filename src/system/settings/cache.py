# -*- coding: utf-8 -*-
from system.env import env


# CACHES
# ------------------------------------------------------------------------------
CACHES = {"default": env.cache("CACHE_URL", default="locmemcache://")}
