# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from .models import *


class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'period', 'type', 'schedule_hour', 'schedule_weekday', 'schedule_timezone', 'schedule_last_send', 'updated', )
    list_display_links = ('id', )
    list_filter = ('project', 'period', 'type', )


admin.site.register(Notification, NotificationAdmin)
