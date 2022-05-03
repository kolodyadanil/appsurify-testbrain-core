# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from .models import *



class GitHubRepositoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'github_repository_name', 'project', ]
    list_display_links = ['id', ]


admin.site.register(GithubRepository, GitHubRepositoryAdmin)
admin.site.register(GithubHook)
admin.site.register(GithubIssue)
