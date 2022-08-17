
from django import forms
from django.db import models
from django.contrib import admin
from django.contrib.auth.forms import UserCreationForm
from django.contrib.admin import helpers, widgets
from django.shortcuts import render
from django.template.response import TemplateResponse
from django.urls import path

from applications.ml.models import MLModel, MLDataset
from applications.testing.models import TestSuite, Test


class MLModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'test_suite', 'ds_count', 'state', 'created', 'updated')
    list_filter = ['test_suite__project', ]
    raw_id_fields = ['test_suite', 'datasets', ]

    def get_queryset(self, request):
        qs = super(MLModelAdmin, self).get_queryset(request)
        return qs.annotate(_ds_count=models.Count('datasets', distinct=True))

    def ds_count(self, obj):
        return obj._ds_count

    ds_count.short_description = 'datasets'
    ds_count.admin_order_field = '_ds_count'


admin.site.register(MLModel, MLModelAdmin)


class MLDatasetAdmin(admin.ModelAdmin):
    list_display = ('id', 'test_suite', 'test_count', 'state', 'index', 'from_date', 'to_date', 'created', 'updated')
    list_filter = ['test_suite__project', ]
    raw_id_fields = ['test_suite', 'tests', ]

    def get_queryset(self, request):
        qs = super(MLDatasetAdmin, self).get_queryset(request)
        return qs.annotate(_test_count=models.Count('tests', distinct=True))

    def test_count(self, obj):
        return obj._test_count

    test_count.short_description = 'tests'
    test_count.admin_order_field = '_test_count'


admin.site.register(MLDataset, MLDatasetAdmin)


