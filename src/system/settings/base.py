# -*- coding: utf-8 -*-
from pathlib import Path

import environ

env = environ.Env()

BASE_DIR = environ.Path(__file__) - 3

env.read_env(BASE_DIR(".env"))
