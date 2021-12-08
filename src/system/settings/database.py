# -*- coding: utf-8 -*-
from system.env import env


# DATABASES
# ------------------------------------------------------------------------------
DATABASES = {"default": env.db("DATABASE_URL")}
