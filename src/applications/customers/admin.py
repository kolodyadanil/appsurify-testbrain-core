# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import User, Organization, OrganizationUser


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["email", ]
    search_fields = ["email", ]


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "domain", "platform", ]
    search_fields = ["name", ]


@admin.register(OrganizationUser)
class OrganizationUserAdmin(admin.ModelAdmin):
    list_display = ["organization", "user", "is_admin", "is_owner", ]
    search_fields = []

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, extra_context=extra_context)
