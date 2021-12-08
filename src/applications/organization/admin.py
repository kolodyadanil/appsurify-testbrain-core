# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from .base_admin import BaseOrganizationAdmin
from .base_admin import BaseOrganizationOwnerAdmin
from .base_admin import BaseOrganizationUserAdmin
from .base_admin import BaseOwnerInline
from .models import Organization
from .models import OrganizationOwner
from .models import OrganizationUser


class OwnerInline(BaseOwnerInline):
    model = OrganizationOwner


class OrganizationAdmin(BaseOrganizationAdmin):
    inlines = [OwnerInline]


class OrganizationUserAdmin(BaseOrganizationUserAdmin):
    pass


class OrganizationOwnerAdmin(BaseOrganizationOwnerAdmin):
    pass


admin.site.register(Organization, OrganizationAdmin)
admin.site.register(OrganizationUser, OrganizationUserAdmin)
admin.site.register(OrganizationOwner, OrganizationOwnerAdmin)
