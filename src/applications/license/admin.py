# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from .models import *


class LicenseKeyAdmin(admin.ModelAdmin):
    list_display = ['id', 'uuid', 'balance', 'expired', 'default', ]


admin.site.register(LicenseKey, LicenseKeyAdmin)
