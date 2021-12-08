# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from mptt.admin import MPTTModelAdmin
from django.db.models import Count
from .models import *


class LimitedManyToManyFieldsMixin(object):
    limited_manytomany_fields = {}

    def get_formset(self, request, obj=None, **kwargs):
        # Hack! Hook parent obj just in time to use in formfield_for_manytomany
        self.parent_obj = obj
        return super(LimitedManyToManyFieldsMixin, self).get_formset(request, obj, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        # Hack! Hook parent obj just in time to use in formfield_for_manytomany
        self.parent_obj = obj
        return super(LimitedManyToManyFieldsMixin, self).get_form(request, obj, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name in self.limited_manytomany_fields.keys() and hasattr(self, 'parent_obj'):
            query_field = self.limited_manytomany_fields[db_field.name]
            obj = self.parent_obj
            if type(query_field) is tuple:
                query_field, obj_func = query_field
                obj = obj_func(obj)
            kwargs['queryset'] = db_field.rel.to.objects.filter(**{query_field: obj})

        return super(LimitedManyToManyFieldsMixin, self).formfield_for_manytomany(db_field, request, **kwargs)


class AreaAdmin(admin.ModelAdmin):
    list_filter = ('project', )


class BranchAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'commit_count', )
    list_filter = ('project', )

    def get_queryset(self, request):
        qs = super(BranchAdmin, self).get_queryset(request)
        return qs.annotate(_commit_count=Count('commits', distinct=True))

    def commit_count(self, obj):
        return obj._commit_count

    commit_count.short_description = 'Commit Count'
    commit_count.admin_order_field = '_commit_count'


class CommitAdmin(LimitedManyToManyFieldsMixin, admin.ModelAdmin):
    list_display = ('id', 'display_id', 'message', 'area_list', 'branch_list', )
    raw_id_fields = ('areas', )
    # raw_id_fields = ('areas', 'branches', )
    list_filter = ('project', )
    # filter_vertical = ('branches', )
    readonly_fields = ('branches', )
    # limited_manytomany_fields = {'branches': ('commits',)}

    def area_list(self, obj):
        return ', '.join(['{}'.format(area.name) for area in obj.areas.all()])

    def branch_list(self, obj):
        return ', '.join(['{}'.format(branch.name) for branch in obj.branches.all()])


class FileMPTTModelAdmin(MPTTModelAdmin):
    list_filter = ('project', )


admin.site.register(Area, AreaAdmin)
admin.site.register(Branch, BranchAdmin)
admin.site.register(Tag)
admin.site.register(Commit, CommitAdmin)
admin.site.register(ParentCommit)
admin.site.register(File, FileMPTTModelAdmin)
admin.site.register(FileChange)
