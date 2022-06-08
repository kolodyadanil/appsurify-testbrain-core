# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import copy
import datetime
import inspect
import traceback

from django.db import transaction
from collections import OrderedDict

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from rest_framework.serializers import raise_errors_on_nested_writes
from rest_framework.utils import html, model_meta

from rest_framework_recursive.fields import RecursiveField

from applications.api.common.serializers import (
    DynamicFieldsModelSerializer, DynamicFieldsRelatedSerializer,
    TimestampField, ChoiceDisplayField, IntDurationField
)

from applications.organization.utils import get_current_organization
from applications.allauth.account.serializers import UserRelatedSerializer
from applications.project.models import Project
from applications.testing.models import *
from applications.vcs.models import *
from applications.api.project.serializers import ProjectRelatedSerializer
from applications.api.testing.serializers import TestSuiteRelatedSerializer
from applications.api.vcs.serializers import CommitRelatedSerializer
from applications.testing.tools import SpecFlow

from django.db.models import Q


class GraphSerializer(serializers.Serializer):
    timestamp = TimestampField(read_only=True)


class ProjectReportSerializer(DynamicFieldsModelSerializer):
    """
    Base serializer for Project model.
    """

    slug = serializers.SlugField(read_only=True, required=False, allow_blank=True, allow_null=True)
    # users = ProjectUserSerializer(source='project_users', many=True, read_only=True)

    number_of_tests = serializers.SerializerMethodField()
    number_of_skipped_tests = serializers.SerializerMethodField()
    number_of_not_skipped_tests = serializers.SerializerMethodField()
    number_of_defects = serializers.SerializerMethodField()
    number_of_flaky_failure_results = serializers.SerializerMethodField()
    percentage_of_pass_results = serializers.SerializerMethodField()

    defect_summary = serializers.ReadOnlyField()
    integration = serializers.SerializerMethodField()

    class Meta(object):
        model = Project
        fields = '__all__'

    def get_number_of_tests(self, project):
        return project.tests.count()

    def get_number_of_skipped_tests(self, project):
        return project.test_run_results.filter(test_run=project.test_runs.last(),
                                               status=TestRunResult.STATUS_SKIPPED).distinct('test').count()

    def get_number_of_not_skipped_tests(self, project):
        return project.test_run_results.filter(test_run=project.test_runs.last()).exclude(
            status=TestRunResult.STATUS_SKIPPED).distinct('test').count()

    def get_number_of_defects(self, project):
        last_test_run = project.test_runs.last()
        return project.defects.filter(created_by_test_run=last_test_run).count()

    def get_number_of_flaky_failure_results(self, project):
        last_test_run = project.test_runs.last()
        return project.defects.filter(
            Q(found_test_runs=last_test_run) | Q(caused_by_test_runs=last_test_run) |
            Q(reopen_test_runs=last_test_run) | Q(created_by_test_run=last_test_run) |
            Q(closed_test_run=last_test_run),
            type__in=[Defect.TYPE_FLAKY, Defect.TYPE_INVALID_TEST, Defect.TYPE_ENVIRONMENTAL],
        ).count()

    def get_percentage_of_pass_results(self, project):
        # TODO: Need change to last test_run_result
        test_run_result_count = project.test_run_results.filter(test_run=project.test_runs.last()).exclude(
            status=TestRunResult.STATUS_SKIPPED).count()

        if test_run_result_count == 0:
            return 0

        pass_test_run_result_count = project.test_run_results.filter(status=TestRunResult.STATUS_PASS,
                                                                     test_run=project.test_runs.last()).count()
        pass_result_ratio = 100
        try:
            pass_result_ratio = (pass_test_run_result_count * 100) / test_run_result_count
        except ZeroDivisionError:
            pass_result_ratio = 100
        return pass_result_ratio

    def get_integration(self, project):
        data = dict()

        github_integration = self._get_github_integration(project)
        if github_integration:
            data = dict(
                provider='github',
                repository_id=github_integration.id,
                repository_name=github_integration.github_repository_name,
                repository_url='https://github.com/{}'.format(github_integration.github_repository_name)
            )

        git_integration = self._get_local_integration(project)
        if git_integration:
            data.update(dict(
                provider='git',
                repository_id=git_integration.id,
                repository_name=git_integration.git_repository_name,
                repository_url='',
                is_installed_hook=git_integration.is_installed_hook
            ))
        return data

    def _get_github_integration(self, project):
        try:
            return project.github_repository
        except:
            return None

    def _get_local_integration(self, project):
        try:
            return project.git_repository
        except:
            return None


class ProjectAddCommitGraphSerializer(GraphSerializer):
    timestamp = TimestampField(source='ts', read_only=True)
    count = serializers.IntegerField(source='__count', default=0, read_only=True)


class AreaReportSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)

    project = serializers.SerializerMethodField()

    number_of_tests = serializers.IntegerField(source='tests__count', default=0, read_only=True)

    number_of_pass_results = serializers.IntegerField(source='passed_tests__count', default=0, read_only=True)
    number_of_fail_results = serializers.IntegerField(source='failed_tests__count', default=0, read_only=True)
    number_of_broken_results = serializers.IntegerField(source='broken_tests__count', default=0, read_only=True)
    number_of_not_run_results = serializers.IntegerField(source='not_run_tests__count', default=0, read_only=True)

    percentage_of_pass_results = serializers.IntegerField(default=0, read_only=True)
    percentage_of_flaky_failure_results = serializers.IntegerField(default=0, read_only=True)

    def get_project(self, instance):
        if isinstance(instance, TestRunResult):
            return dict(id=instance.project_id, name=instance.project_name)
        elif isinstance(instance, dict):
            return dict(id=instance['project_id'], name=instance['project_name'])
        else:
            return dict()


class AreaByTestChartSerializer(serializers.Serializer):
    name = serializers.CharField(read_only=True)
    count = serializers.IntegerField(source='__count', default=0, read_only=True)


class AreaBugspotReportSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    commits = serializers.ListField(child=serializers.DictField())


class FileReportSerializer(DynamicFieldsModelSerializer):
    # has_childs = serializers.SerializerMethodField()
    has_childs = serializers.ReadOnlyField()
    # is_associated = serializers.SerializerMethodField()
    is_associated = serializers.ReadOnlyField(default=False)

    # rank = serializers.SerializerMethodField()
    rank = serializers.ReadOnlyField(default='green')

    class Meta(object):
        model = File
        # fields = ('id', 'filename', 'has_childs')
        fields = '__all__'

    # def get_has_childs(self, obj):
    #     if obj.get_descendant_count() > 0:
    #         return True
    #     return False
    #
    # def get_is_associated(self, obj):
    #     return getattr(obj, 'is_associated', False)

    # def get_rank(self, obj):
    #     rank = 'green'
    #     try:
    #         hotspots = self.context['hotspots']
    #         red_hotspots = self.context['red_hotspots']
    #         orange_hotspots = self.context['orange_hotspots']
    #         green_hotspots = self.context['green_hotspots']
    #
    #         for hotspot in red_hotspots:
    #             filename = hotspot.filename
    #             part_full_filename = filename[:len(obj.full_filename)]
    #             if part_full_filename == obj.full_filename:
    #                 rank = 'red'
    #                 return rank
    #
    #         for hotspot in orange_hotspots:
    #             filename = hotspot.filename
    #             part_full_filename = filename[:len(obj.full_filename)]
    #             if part_full_filename == obj.full_filename:
    #                 rank = 'orange'
    #                 return rank
    #
    #         for hotspot in green_hotspots:
    #             filename = hotspot.filename
    #             part_full_filename = filename[:len(obj.full_filename)]
    #             if part_full_filename == obj.full_filename:
    #                 rank = 'green'
    #                 return rank
    #
    #     except Exception, e:
    #         pass
    #
    #     return rank


class FileReportRelatedSerializer(DynamicFieldsRelatedSerializer):
    class Meta(object):
        model_class = File
        model_serializer_class = FileReportSerializer


class TestTypeReportSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class TestSuiteReportSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)

    project = serializers.SerializerMethodField()

    number_of_tests = serializers.IntegerField(source='tests__count', default=0, read_only=True)
    number_of_new_defects = serializers.IntegerField(source='created_defects__count', default=0, read_only=True)
    number_of_flaky_failure_results = serializers.IntegerField(source='founded_defects__flaky_failure__count',
                                                               default=0, read_only=True)

    number_of_pass_results = serializers.IntegerField(source='passed_tests__count', default=0, read_only=True)
    number_of_fail_results = serializers.IntegerField(source='failed_tests__count', default=0, read_only=True)
    number_of_broken_results = serializers.IntegerField(source='broken_tests__count', default=0, read_only=True)
    number_of_not_run_results = serializers.IntegerField(source='not_run_tests__count', default=0, read_only=True)

    percentage_of_pass_results = serializers.IntegerField(default=0, read_only=True)
    percentage_of_flaky_failure_results = serializers.IntegerField(default=0, read_only=True)

    test_run_id = serializers.IntegerField(allow_null=True, read_only=True)

    def get_project(self, instance):
        if isinstance(instance, TestRunResult):
            return dict(id=instance.project_id, name=instance.project_name)
        elif isinstance(instance, dict):
            return dict(id=instance['project_id'], name=instance['project_name'])
        else:
            return dict()


class TestRunReportSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)

    project = serializers.JSONField(read_only=True, source='_project')
    test_suite = serializers.JSONField(read_only=True, source='_test_suite')

    start_date = serializers.DateTimeField(read_only=True, source='_start_date')
    end_date = serializers.DateTimeField(read_only=True, source='_end_date')

    execution_time = serializers.FloatField(source='tests__execution_time', default=0.0, read_only=True)

    previous_execution_time = serializers.FloatField(source='previous_test_run_execution_time.execution_time',
                                                     default=0.0, read_only=True)

    number_of_new_defects = serializers.IntegerField(
        source='created_defect_count.created_defects_count', default=0, read_only=True)
    number_of_flaky_failure_results = serializers.IntegerField(
        source='founded_defect_count.founded_defects_flaky_failure_count', default=0, read_only=True)

    number_of_tests = serializers.IntegerField(source='tests__count', default=0, read_only=True)
    number_of_pass_results = serializers.IntegerField(source='passed_tests__count', default=0, read_only=True)
    number_of_fail_results = serializers.IntegerField(source='failed_tests__count', default=0, read_only=True)
    number_of_broken_results = serializers.IntegerField(source='broken_tests__count', default=0, read_only=True)
    number_of_not_run_results = serializers.IntegerField(source='not_run_tests__count', default=0, read_only=True)
    # number_of_skipped_results = serializers.IntegerField(source='skipped_tests__count', default=0, read_only=True)

    status = serializers.CharField(read_only=True, source='tests__status')
    # status = serializers.SerializerMethodField(method_name="get_status")
    # percentage_of_pass_results = serializers.IntegerField(default=0, read_only=True)
    # percentage_of_flaky_failure_results = serializers.IntegerField(default=0, read_only=True)
    #
    # def get_skipped_tests_count(self, instance):
    #     test_runs = TestRun.objects.filter(test_suite=instance.test_suite_id).values()
    #     current_date = test_runs[len(test_runs)-1]['start_date']
    #     minus60days = current_date - datetime.timedelta(days=60)
    #     for test_run in test_runs:
    #         if test_run['start_date'] >= minus60days and test_run['start_date'] <= current_date:
    #             test_result = TestRunResult.objects.filter(test_suite=instance.test_suite_id, test_run_id=test_run['id']).values()
    #             tests_num = len(test_result)
    #             if tests_num > self.std_num:
    #                 self.std_num = tests_num
    #
    #     skipped_results = self.std_num - instance.mv_test_count_by_type.passed_tests_count - \
    #                       instance.mv_test_count_by_type.failed_tests_count - instance.mv_test_count_by_type.broken_tests_count
    #     self.std_num = 0
    #     return skipped_results


class TestRunReportByDaySerializer(serializers.Serializer):
    test_runs = serializers.IntegerField(source='test_runs__count', default=0, read_only=True)
    day = serializers.CharField()
    number_of_tests = serializers.IntegerField(source='tests__count', default=0, read_only=True)
    execution_time = serializers.FloatField(default=0, read_only=True)
    standard_execution_time = serializers.SerializerMethodField(method_name="get_standard_execution_time")
    standard_test_number = serializers.SerializerMethodField(method_name="get_standard_test_number")
    number_of_pass_results = serializers.IntegerField(source='passed_tests__count', default=0, read_only=True)
    number_of_fail_results = serializers.IntegerField(source='failed_tests__count', default=0, read_only=True)
    number_of_broken_results = serializers.IntegerField(source='broken_tests__count', default=0, read_only=True)
    number_of_not_run_results = serializers.IntegerField(source='not_run_tests__count', default=0, read_only=True)

    def get_standard_test_number(selfself, instance):
        return instance['standard_test_runs']

    def get_standard_execution_time(self, instance):
        """
        Tbh, Idk the calculation of the standard time
        """
        max_execution_time = instance.get("max_execution_time", 0)
        if not max_execution_time:
            max_execution_time = 0
        return max_execution_time * instance.get("test_runs__count", 0) * instance.get(
            "tests__count", 0)


class TestRunDetailReportSerializer(DynamicFieldsModelSerializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    project = ProjectRelatedSerializer(fields=('id', 'name'), queryset=Project.objects.all())
    test_suite = TestSuiteRelatedSerializer(fields=('id', 'name'), queryset=TestSuite.objects.all())

    number_of_fail_results = serializers.IntegerField(default=0, read_only=True)
    percentage_of_flaky_failure_results = serializers.IntegerField(default=0, read_only=True)

    execution_time = serializers.IntegerField(default=0, read_only=True)
    execution_time_avg = serializers.IntegerField(default=0, read_only=True)
    test_run_results_summary = serializers.ReadOnlyField()

    previous_test_run = serializers.SerializerMethodField()

    class Meta(object):
        model = TestRun
        fields = (
            'id',
            'name',
            'project',
            'test_suite',
            'execution_time',
            'execution_time_avg',
            'test_run_results_summary',
            'number_of_fail_results',
            'percentage_of_flaky_failure_results',
            'previous_test_run'
        )

    def get_previous_test_run(self, test_run):
        # print '####', test_run
        # print '####', test_run.previous_test_run
        serializer = TestRunDetailReportSerializer(test_run.previous_test_run, allow_null=True, many=False,
                                                   fields=(
                                                       'id',
                                                       'name',
                                                       'execution_time',
                                                       'execution_time_avg',
                                                       'test_run_results_summary',
                                                       'number_of_fail_results',
                                                       'percentage_of_flaky_failure_results'))
        return serializer.data


class TestReportSerializer(DynamicFieldsModelSerializer):
    project = ProjectRelatedSerializer(fields=('id', 'name'), read_only=True, many=False)
    test_suites = TestSuiteRelatedSerializer(fields=('id', 'name'), read_only=True, many=True)
    current_status = serializers.CharField(read_only=True)

    class Meta(object):
        model = Test
        exclude = ()


class TestExecutionTimeGraphSerializer(GraphSerializer):
    passed = serializers.IntegerField(source='__passed_count', default=0, read_only=True)
    failed = serializers.IntegerField(source='__failed_count', default=0, read_only=True)
    broken = serializers.IntegerField(source='__broken_count', default=0, read_only=True)


class TestExecutionTimeAvgGraphSerializer(GraphSerializer):
    execution_time_avg = serializers.FloatField(source='__execution_time', default=0.0, read_only=True)


class TestStatusPassedGraphSerializer(GraphSerializer):
    # count = serializers.IntegerField(source='__count', default=0, read_only=True)
    percentage_of_passed_results = serializers.IntegerField(default=0, read_only=True)


class TestFlakinessReportSerializer(TestReportSerializer):
    number_of_flaky_failure_results = serializers.IntegerField(source='flaky_failure__count', default=0, read_only=True)
    percentage_of_flaky_failure_results = serializers.FloatField(default=float(), read_only=True)
    results = serializers.ListSerializer(source='last_test_run_results', child=serializers.ReadOnlyField(),
                                         default=list(), read_only=True, allow_null=True, allow_empty=True)


class TestChangedReportSerializer(TestReportSerializer):
    current_status = serializers.CharField(read_only=True)
    previous_status = serializers.CharField(read_only=True)


class TestSlowestReportSerializer(TestReportSerializer):
    execution_time_min = serializers.IntegerField(default=0, read_only=True)
    execution_time_avg = serializers.IntegerField(default=0, read_only=True)
    execution_time_max = serializers.IntegerField(default=0, read_only=True)
    execution_time_diff = serializers.SerializerMethodField()

    def get_execution_time_diff(self, instance):
        try:
            return (instance['execution_time_max'] * 100) / instance['execution_time_avg']
        except ZeroDivisionError:
            return 0
        except AttributeError:
            return 0


class TestRunResultReportSerializer(DynamicFieldsModelSerializer):
    class Meta(object):
        model = TestRunResult
        fields = '__all__'


class DefectReportSerializer(DynamicFieldsModelSerializer):
    project = ProjectRelatedSerializer(fields=('id', 'name'), queryset=Project.objects.all())
    owner = UserRelatedSerializer(fields=('id', 'username'), queryset=User.objects.all(), required=False)
    priority = serializers.IntegerField(default=1, min_value=1, max_value=10)

    passed_associated_tests = serializers.ListSerializer(
        child=TestReportSerializer(read_only=True),
        read_only=True,
        allow_null=True,
        allow_empty=True
    )
    failed_associated_tests = serializers.ListSerializer(
        child=TestReportSerializer(read_only=True),
        read_only=True,
        allow_null=True,
        allow_empty=True
    )
    broken_associated_tests = serializers.ListSerializer(
        child=TestReportSerializer(read_only=True),
        read_only=True,
        allow_null=True,
        allow_empty=True
    )
    not_run_associated_tests = serializers.ListSerializer(
        child=TestReportSerializer(read_only=True),
        read_only=True,
        allow_null=True,
        allow_empty=True
    )

    found_commits = CommitRelatedSerializer(fields=('id', 'display_id', 'message', 'url'),
                                            queryset=Commit.objects.all(), many=True, required=False, allow_empty=True,
                                            allow_null=True)
    caused_by_commit = CommitRelatedSerializer(fields=('id', 'display_id', 'message', 'url'),
                                               queryset=Commit.objects.all(), required=False, allow_empty=True,
                                               allow_null=True)

    class Meta(object):
        model = Defect
        fields = '__all__'


class DefectSeverityReportSerializer(serializers.Serializer):
    trivial = serializers.DictField(default=dict(new=0, in_progress=0, ready=0, closed=0), read_only=True)
    minor = serializers.DictField(default=dict(new=0, in_progress=0, ready=0, closed=0), read_only=True)
    major = serializers.DictField(default=dict(new=0, in_progress=0, ready=0, closed=0), read_only=True)
    critical = serializers.DictField(default=dict(new=0, in_progress=0, ready=0, closed=0), read_only=True)

    class Meta(object):
        fields = '__all__'


class DefectSummaryReportSerializer(serializers.Serializer):

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    severity = DefectSeverityReportSerializer(read_only=True)
    create_type = serializers.ReadOnlyField()
    number_of_defects = serializers.ReadOnlyField()
    number_of_open_defects = serializers.ReadOnlyField()

    class Meta(object):
        fields = '__all__'


class DefectCloseDurationTimeGraphSerializer(GraphSerializer):
    duration = IntDurationField(source='__duration', default=0, read_only=True)


class DefectOpenStatusGraphSerializer(GraphSerializer):
    count = serializers.IntegerField(source='__count', default=0, read_only=True)


class DefectNewStatusGraphSerializer(GraphSerializer):
    count = serializers.IntegerField(source='__count', default=0, read_only=True)


class SeverityGraphSerializer(GraphSerializer):
    trivial = serializers.IntegerField(source='__count_trivial', default=0, read_only=True)
    minor = serializers.IntegerField(source='__count_minor', default=0, read_only=True)
    major = serializers.IntegerField(source='__count_major', default=0, read_only=True)
    critical = serializers.IntegerField(source='__count_critical', default=0, read_only=True)


class DefectByTypeChartSerializer(serializers.Serializer):
    type = ChoiceDisplayField(choices=Defect.TYPE_CHOICE, display_only=True, read_only=True)
    count = serializers.IntegerField(source='__count', default=0, read_only=True)


class AnalysisRangeGraphSerializer(serializers.Serializer):
    commits = serializers.FloatField(default=0)
    output = serializers.FloatField(default=0)
    rework = serializers.FloatField(default=0)
    defects = serializers.FloatField(default=0)


class AnalysisFullUsernameSerializer(serializers.Serializer):
    username = serializers.ListField(default=list())


class AnalysisUserSerializer(serializers.Serializer):
    hour = serializers.DictField(default=dict())
    one_weekday = serializers.DictField(default=dict())
    today = serializers.DictField(default=dict())
    weekday = serializers.DictField(default=dict())
    all_day = serializers.DictField(default=dict())


class AnalysisTeamSerializer(serializers.Serializer):
    users = serializers.ListField(read_only=True)
    avg = serializers.DictField(read_only=True)
    max_output = serializers.FloatField(default=0)
    max_commits = serializers.FloatField(default=0)


class AnalysisTeamsSerializer(serializers.Serializer):
    users = serializers.ListField(read_only=True)
    avg = serializers.DictField(read_only=True)
    max_output = serializers.FloatField(default=0)
    max_commits = serializers.FloatField(default=0)