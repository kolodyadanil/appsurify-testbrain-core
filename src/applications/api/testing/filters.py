# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db.models.constants import LOOKUP_SEP
from rest_framework_filters import FilterSet, CharFilter, NumberFilter, OrderingFilter, BooleanFilter

from applications.testing.models import *
from applications.vcs.models import *


class TestTypeFilterSet(FilterSet):

    class Meta(object):
        model = TestType
        fields = ('project', )


class TestSuiteFilterSet(FilterSet):

    class Meta(object):
        model = TestSuite
        fields = ('project', )


class TestRunFilterSet(FilterSet):

    class Meta(object):
        model = TestRun
        fields = ('project', )


class TestFilterSet(FilterSet):

    test_suite = NumberFilter(label='test_suites__id', method='filter_test_suite')
    test_run = NumberFilter(label='test_runs__id', method='filter_test_run')

    class Meta(object):
        model = Test
        fields = ('project', 'area', 'test_run', 'test_suite', )

    def filter_test_run(self, qs, name, value):
        lookup_expr = LOOKUP_SEP.join([name, ])
        qs = qs.filter(**{lookup_expr: value}).distinct()
        return qs

    def filter_test_suite(self, qs, name, value):
        lookup_expr = LOOKUP_SEP.join([name, ])
        qs = qs.filter(**{lookup_expr: value}).distinct()
        return qs


class StepFilterSet(FilterSet):

    class Meta(object):
        model = Step
        fields = ('project', )


class TestRunResultFilterSet(FilterSet):

    class Meta(object):
        model = TestRunResult
        fields = ('project', 'test_type', 'test_suite', 'test_run', 'area', 'test', )


class DefectFilterSet(FilterSet):

    test_run = NumberFilter(label='found_test_runs__id', method='filter_test_run')

    class Meta(object):
        model = Defect
        fields = ('project', 'owner', 'owner__username', 'status', 'type', 'test_run',)

    def filter_test_run(self, qs, name, value):
        lookup_expr = LOOKUP_SEP.join([name, ])
        qs = qs.filter(**{lookup_expr: value}).distinct()
        return qs

class FileFilterSet(FilterSet):

    area = NumberFilter(label='area', method='filter_is_associated')

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

