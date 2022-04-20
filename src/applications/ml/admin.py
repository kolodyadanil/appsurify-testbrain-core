# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import MLModel


class MLModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'test_suite', 'state', 'index', 'fr', 'to', 'created', 'updated')


admin.site.register(MLModel, MLModelAdmin)
