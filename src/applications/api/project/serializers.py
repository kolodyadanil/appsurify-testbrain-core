# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# from djangotasks.models import Task
import datetime
from enum import Enum
from functools import reduce

import pytz
from drf_yasg.utils import swagger_serializer_method
from rest_framework import serializers

from applications.api.common.serializers import DynamicFieldsModelSerializer, DynamicFieldsRelatedSerializer
from applications.project.models import *
from applications.testing.models import *


class ProjectUserSerializer(DynamicFieldsModelSerializer):
    id = serializers.ReadOnlyField(source='user.id')
    username = serializers.ReadOnlyField(source='user.username')
    email = serializers.ReadOnlyField(source='user.email')

    is_owner = serializers.SerializerMethodField()

    class Meta(object):
        model = ProjectUser
        fields = ('id', 'username', 'email', 'is_owner',)

    def get_is_owner(self, user):
        project = user.project
        return project.is_owner(user.user)


class BaseProjectSerializer(DynamicFieldsModelSerializer):
    def get_number_of_tests(self, project):
        return project.tests.count()

    def get_number_of_defects(self, project):
        return project.defects.count()

    def get_number_of_flaky_failure_results(self, project):
        return project.defects.filter(
            type__in=[Defect.TYPE_FLAKY, Defect.TYPE_INVALID_TEST, Defect.TYPE_ENVIRONMENTAL]
        ).count()

    def get_percentage_of_pass_results(self, project):
        # TODO: Need change to last test_run_result
        test_run_result_count = project.test_run_results.count()

        if test_run_result_count == 0:
            return 0

        pass_test_run_result_count = project.test_run_results.filter(status=TestRunResult.STATUS_PASS).count()
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

        bitbucket_integration = self._get_bitbucket_integration(project)
        if bitbucket_integration:
            data.update(dict(
                provider='bitbucket',
                repository_id=bitbucket_integration.id,
                repository_name=bitbucket_integration.bitbucket_repository_name,
                repository_url='https://bitbucket.org/{}'.format(bitbucket_integration.bitbucket_repository_name),
            ))

        ssh_integration = self._get_ssh_integration(project)
        if ssh_integration:
            data.update(dict(
                provider='ssh',
                repository_id=ssh_integration.id,
                repository_name=ssh_integration.repository_name,
                repository_url=ssh_integration.url_repository,
                hook_url=ssh_integration.get_hook_url()
            ))
        perforce_integration = self._get_perforce_integration(project)
        if perforce_integration:
            data.update(dict(
                provider='perforce',
                repository_id=perforce_integration.id,
                repository_name=perforce_integration.depot,
                repository_url=perforce_integration.depot,
                repository_depot=perforce_integration.depot
            ))
        ssh_v2_integration = self._get_ssh_v2_integration(project)
        if ssh_v2_integration:
            data.update(dict(
                provider='ssh_v2',
                repository_id=ssh_v2_integration.id,
                repository_name=ssh_v2_integration.repository_name,
                repository_url='',
                is_installed_hook=ssh_v2_integration.is_installed_hook
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

    def _get_bitbucket_integration(self, project):
        try:
            return project.bitbucket_repository
        except:
            return None

    def _get_ssh_integration(self, project):
        try:
            return project.git_ssh_repository
        except:
            return None

    def _get_ssh_v2_integration(self, project):
        try:
            return project.git_ssh_v2_repository
        except:
            return None

    def _get_perforce_integration(self, project):
        try:
            return project.perforce_repository
        except:
            return None

    def get_import_status(self, project):
        status = None
        # from django_celery_results.models import TaskResult
        # github_integration = self._get_github_integration(project)
        # if github_integration:
        #     try:
        #         status = TaskResult.objects.filter(
        #             task_name='applications.integration.tasks.fetch_commits_task',
        #             task_args=[github_integration.id, u'githubrepository'].__str__()
        #         ).order_by('date_done').last().status
        #         status = str(status).lower()
        #     except:
        #         status = None
        # git_integration = self._get_local_integration(project)
        # if git_integration:
        #     try:
        #         status = TaskResult.objects.filter(
        #             task_name='applications.integration.tasks.fetch_commits_task',
        #             task_args=[git_integration.id, u'gitrepository'].__str__()
        #         ).order_by('date_done').last().status
        #         status = str(status).lower()
        #     except:
        #         status = None
        # bitbucket_integration = self._get_bitbucket_integration(project)
        # if bitbucket_integration:
        #     try:
        #         status = TaskResult.objects.filter(
        #             task_name='applications.integration.tasks.fetch_commits_task',
        #             task_args=[bitbucket_integration.id, u'bitbucketrepository'].__str__()
        #         ).order_by('date_done').last().status
        #         status = str(status).lower()
        #     except:
        #         status = None
        # ssh_integration = self._get_ssh_integration(project)
        # if ssh_integration:
        #     try:
        #         status = TaskResult.objects.filter(
        #             task_name='applications.integration.tasks.fetch_commits_task',
        #             task_args=[ssh_integration.id, u'gitsshrepository'].__str__()
        #         ).order_by('date_done').last().status
        #         status = str(status).lower()
        #     except:
        #         status = None
        #
        # perforce_integration = self._get_perforce_integration(project)
        # if perforce_integration:
        #     try:
        #         status = TaskResult.objects.filter(
        #             task_name='applications.integration.tasks.fetch_commits_task',
        #             task_args=[perforce_integration.id, u'perforcerepository', False].__str__()
        #         ).order_by('date_done').last().status
        #         status = str(status).lower()
        #     except:
        #         status = None
        #
        # ssh_v2_integration = self._get_ssh_v2_integration(project)
        # if ssh_v2_integration:
        #     status = str('success').lower()
        status = str('success').lower()
        return status


class ProjectSerializer(BaseProjectSerializer):
    """
    Base serializer for Project model.
    """

    slug = serializers.SlugField(read_only=True, required=False, allow_blank=True, allow_null=True)

    users = ProjectUserSerializer(source='project_users', many=True, read_only=True)

    number_of_tests = serializers.SerializerMethodField()
    number_of_defects = serializers.SerializerMethodField()
    number_of_flaky_failure_results = serializers.SerializerMethodField()
    percentage_of_pass_results = serializers.SerializerMethodField()

    defect_summary = serializers.ReadOnlyField()
    integration = serializers.SerializerMethodField()
    import_status = serializers.SerializerMethodField()

    class Meta(object):
        model = Project
        fields = '__all__'


class ProjectRelatedSerializer(DynamicFieldsRelatedSerializer):
    class Meta(object):
        model_class = Project
        model_serializer_class = ProjectSerializer


class ProjectStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESSFUL = "SUCCESSFUL"
    FAILURE = "FAILURE"


project_status_choices = [e.value for e in ProjectStatus]


class ProjectSetupStatusSerializer(serializers.Serializer):
    repo_bind = serializers.ChoiceField(choices=project_status_choices)
    test_bind = serializers.ChoiceField(choices=project_status_choices)
    building_model = serializers.ChoiceField(choices=project_status_choices)


class ProjectTestRunStats(serializers.Serializer):
    count = serializers.IntegerField()
    failed = serializers.IntegerField()
    passed = serializers.IntegerField()
    broken = serializers.IntegerField()
    skipped = serializers.IntegerField()
    execution_time_seconds = serializers.FloatField()
    time_savings_seconds = serializers.FloatField()


class ProjectSummarySerializer(BaseProjectSerializer):
    """
    Aggregates data to display on the updated dashboard.
    """

    class Meta(object):
        model = Project
        fields = ('id', 'name', 'setup_status', 'maturity', "stats")

    @swagger_serializer_method(serializer_or_field=serializers.FloatField)
    def get_maturity(self, project):
        """
        Maturity is 100% after 50 test runs. Every tests run add 2%
        """
        count_test_runs = len(TestRun.objects.filter(project=project))
        if count_test_runs >= 50:
            maturity = 1.0
        else:
            maturity = count_test_runs / 50
        return maturity

    @swagger_serializer_method(serializer_or_field=ProjectTestRunStats)
    def get_stats(self, project):
        """
        Gives stats for summary page related to tests.
        """
        # Take 20 latest test run ids for project (ordered by date)
        latest_query_ids = list(
            map(lambda x: x.pk, TestRun.objects.filter(project=project).order_by("-start_date")[:20]))

        # Honestly, I have no idea if it's a correct way to calculate total saved time
        # Take the max execution time for latest 20 test runs and then subtract this maximum per each test run
        # TODO: consult if it's a correct way of calculating this.
        # Filter expression for queryset
        filter_dict = dict(project=project, test_run_id__in=latest_query_ids)

        # Find max execution time for the TestRun
        # Group by test_run_id
        execution_time_by_test_run = TestRunResult.objects.filter(**filter_dict).values('test_run_id').annotate(
            sum=models.Sum('execution_time'))
        standard_execution_time = execution_time_by_test_run.aggregate(max=models.Max('sum'))['max']
        # TODO: this is a way to avoid 500 while we have no data for execution_time_by_test_run after project creation
        if not execution_time_by_test_run:
            time_savings_seconds = 0
        else:
            time_savings_seconds = reduce(lambda x, y: x + y,
                                          map(lambda x: standard_execution_time - x['sum'], execution_time_by_test_run))

        return dict(
            **TestRunResult.objects.filter(**filter_dict).aggregate(
                count=models.Count("id"),
                execution_time_seconds=models.Sum('execution_time'),
                failed=models.Count(
                    models.Case(models.When(models.Q(status=TestRunResult.STATUS_FAIL), then=models.F('id')))),
                passed=models.Count(
                    models.Case(models.When(models.Q(status=TestRunResult.STATUS_PASS), then=models.F('id')))),
                broken=models.Count(
                    models.Case(models.When(models.Q(status=TestRunResult.STATUS_BROKEN), then=models.F('id')))),
                skipped=models.Count(
                    models.Case(models.When(models.Q(status=TestRunResult.STATUS_SKIPPED), then=models.F('id')))),
            ),
            time_savings_seconds=time_savings_seconds)

    @swagger_serializer_method(serializer_or_field=ProjectSetupStatusSerializer)
    def get_setup_status(self, project):
        """
        Checks if test suite exists, repo is linked and if ml model is created and processed.
        """
        integration = self.get_integration(project)
        # Check if there's a test suite created. (Are we taking the first test suite added to the system?)
        # TODO: Clarify this later
        # From requirements:
        # No Test Bind phase needs to be completed after a test run has been sent
        # I think we can ignore testing at the test bind stage atm
        # So green if sent data, grey if it hasn't
        # Red if it had sent data but hasn't sent any within the 8 days
        test_suite = project.test_suites.first()

        # If the integration is not set up an empty dict is returned.
        repo_bind = ProjectStatus.SUCCESSFUL if len(integration) > 0 else ProjectStatus.NOT_STARTED
        utc = pytz.UTC
        if project.test_run_results.all():
            test_bind = ProjectStatus.SUCCESSFUL
        elif project.created < (datetime.datetime.today() - datetime.timedelta(days=8)).replace(
                tzinfo=utc) and test_suite == ProjectStatus.SUCCESSFUL:
            test_bind = ProjectStatus.FAILURE
        else:
            test_bind = ProjectStatus.NOT_STARTED

        building_model = ProjectStatus.NOT_STARTED

        # model = test_suite.model if test_suite else None
        # if model:
        #     status = model.model_status
        #     if status == "SUCCESS":
        #         building_model = ProjectStatus.SUCCESSFUL
        #     elif status == "FAILURE":
        #         building_model = ProjectStatus.FAILURE
        #     else:
        #         building_model = ProjectStatus.NOT_STARTED

        return dict(
            repo_bind=repo_bind,
            test_bind=test_bind,
            building_model=building_model)

    setup_status = serializers.SerializerMethodField()
    maturity = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()
