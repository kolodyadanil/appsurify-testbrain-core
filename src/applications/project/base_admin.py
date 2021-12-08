# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin


class BaseOwnerInline(admin.StackedInline):
    raw_id_fields = ('project_user',)


class BaseProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']
    list_filter = ('is_active',)


class BaseProjectUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'project']
    raw_id_fields = ('user', 'project')


class BaseProjectOwnerAdmin(admin.ModelAdmin):
    raw_id_fields = ('project_user', 'project')
