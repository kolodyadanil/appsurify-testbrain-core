# -*- coding: utf-8 -*-

from django.contrib import admin
from .models import Repository, Event, Change


admin.site.register(Repository)
admin.site.register(Event)
admin.site.register(Change)
