#-*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db.models.constants import LOOKUP_SEP
from rest_framework_filters import *
from django_filters.fields import Lookup


from applications.api.common.filters import BaseFilterSet
from applications.project.models import Project
from applications.testing.models import *
from applications.vcs.models import *


class ListFilter(Filter):

    def filter(self, qs, value):
        value_list = [x.lstrip().rstrip() for x in value.split(u',')]
        return super(ListFilter, self).filter(qs, Lookup(value_list, 'in'))


class ProjectReportFilterSet(FilterSet):

    class Meta(object):
        model = Project
        fields = ()


class AreaReportFilterSet(FilterSet):

    class Meta(object):
        model = TestRunResult
        fields = ('project', 'test_run', )


class FileReportFilterSet(FilterSet):

    area = NumberFilter(label='area', method='filter_is_associated')

    class Meta(object):
        model = File
        fields = ('project', 'area',)

    def filter_is_associated(self, qs, name, value):
        # area = Area.objects.filter(id=value, files=models.OuterRef('pk'))
        # qs = qs.annotate(
        #     is_associated=models.Exists(area)
        # )
        return qs


class CommitReportFilterSet(FilterSet):

    area = NumberFilter(label='areas__id', method='filter_area')

    class Meta(object):
        model = Commit
        fields = ('project', 'area', )

    def filter_area(self, qs, name, value):
        lookup_expr = LOOKUP_SEP.join([name, ])
        qs = qs.filter(**{lookup_expr: value}).distinct()
        return qs


class TestTypeReportFilterSet(FilterSet):

    class Meta(object):
        model = TestRunResult
        fields = ('project', )


class TestSuiteReportFilterSet(FilterSet):

    class Meta(object):
        model = TestRunResult
        fields = ('project', )


class TestRunReportFilterSet(FilterSet):

    type = NumberFilter(label='test_run_type')
    status = NumberFilter(label='test_run_status')
    is_local = BooleanFilter(label='test_run_is_local')

    class Meta(object):
        model = TestRunResult
        fields = ('project', 'test_suite', 'type', 'status', 'is_local')


class TestReportFilterSet(FilterSet):
    project = NumberFilter(label='project__id')
    area = NumberFilter(label='area__id')
    test_suite = NumberFilter(label='test_suites__id')
    test_run = NumberFilter(label='test_runs__id')
    # test_run = NumberFilter(label='test_runs__id')
    # is_local = BooleanFilter(label='test_runs__is_local')

    class Meta(object):
        model = Test
        fields = ('project', 'area', 'test_suite', 'test_run', )


class TestRunResultReportFilterSet(FilterSet):

    class Meta(object):
        model = TestRunResult
        fields = ('project', 'test_type', 'test_suite', 'test_run', 'area', 'test', )


class DefectReportFilterSet(FilterSet):

    test_run = NumberFilter(label='found_test_runs__id')

    class Meta(object):
        model = Defect
        # fields = ('project', 'owner', 'owner__username', 'status', 'type', 'test_run',)
        fields = ('project', 'status', 'type', 'owner', 'test_run',)


