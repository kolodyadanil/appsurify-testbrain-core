# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.http.request
from django.db.models.constants import LOOKUP_SEP
from rest_framework_filters import FilterSet, CharFilter, NumberFilter, RelatedFilter, BooleanFilter

from applications.vcs.models import *


class AreaFilterSet(FilterSet):

    show_default = BooleanFilter(field_name='show_default', method='filter_show_default')
    only_empty = BooleanFilter(field_name='only_empty', method='filter_only_empty')
    functional_areas = BooleanFilter(field_name='functional_areas', method='filter_functional_areas')
    test_areas = BooleanFilter(field_name='test_areas', method='filter_test_areas')

    class Meta(object):
        model = Area
        fields = ('project', 'show_default', 'only_empty')

    def __init__(self, *args, **kwargs):
        super(AreaFilterSet, self).__init__(*args, **kwargs)

    @property
    def qs(self):
        if isinstance(self.data, django.http.request.QueryDict):
            setattr(self.data, '_mutable', True)

        if not self.data.has_key('show_default'):
            self.data['show_default'] = False
        else:
            if self.data['show_default'] == u'':
                self.data['show_default'] = False

        qs = super(AreaFilterSet, self).qs
        return qs

    def filter_show_default(self, qs, name, value):
        if not value:
            qs = qs.exclude(name='Default Area')
        return qs

    def filter_only_empty(self, qs, name, value):
        qs = qs.filter(tests__isnull=value).distinct()
        return qs

    def filter_functional_areas(self, qs, name, value):
        qs = qs.filter(~models.Q(files__isnull=value)).distinct()
        return qs

    def filter_test_areas(self, qs, name, value):
        qs = qs.filter(~models.Q(tests__isnull=value)).distinct()
        return qs


class CommitFilterSet(FilterSet):

    class Meta(object):
        model = Commit
        fields = ('project', 'branches', )


class BranchFilterSet(FilterSet):

    class Meta(object):
        model = Branch
        fields = ('project', )


class TagFilterSet(FilterSet):

    class Meta(object):
        model = Tag
        fields = ('project', )


class FileFilterSet(FilterSet):

    area = NumberFilter(name='area', method='filter_is_associated')

    class Meta(object):
        model = File
        fields = ('project', 'area',)

    def filter_is_associated(self, qs, name, value):
        area = Area.objects.filter(id=value, files=models.OuterRef('pk'))
        qs = qs.annotate(
            is_associated=models.Exists(area),
            is_area=models.Value(value, output_field=models.IntegerField())
        )
        return qs


