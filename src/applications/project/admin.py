# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from .base_admin import BaseProjectAdmin
from .base_admin import BaseProjectOwnerAdmin
from .base_admin import BaseProjectUserAdmin
from .base_admin import BaseOwnerInline
from .models import Project
from .models import ProjectOwner
from .models import ProjectUser


class OwnerInline(BaseOwnerInline):
    model = ProjectOwner


class ProjectAdmin(BaseProjectAdmin):
    inlines = [OwnerInline]


class ProjectUserAdmin(BaseProjectUserAdmin):
    pass


class ProjectOwnerAdmin(BaseProjectOwnerAdmin):
    pass


admin.site.register(Project, ProjectAdmin)
admin.site.register(ProjectUser, ProjectUserAdmin)
admin.site.register(ProjectOwner, ProjectOwnerAdmin)
