# -*- coding: utf-8 -*-
import environ
from pathlib import Path

env = environ.Env()

BASE_DIR = Path(__file__).resolve().parent.parent

env.read_env(BASE_DIR / ".." / ".env")
