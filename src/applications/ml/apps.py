# -*- coding: utf-8 -*-
from django.apps import AppConfig


class MLConfig(AppConfig):
    name = "applications.ml"
    verbose_name = "ML"
    
    def ready(self):
        ...
