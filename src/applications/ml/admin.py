# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import MLModel


class MLModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'test_suite', 'dataset_status', 'model_status', 'created', 'updated')


admin.site.register(MLModel, MLModelAdmin)
