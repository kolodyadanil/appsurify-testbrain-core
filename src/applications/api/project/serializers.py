# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# from djangotasks.models import Task
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


class ProjectSerializer(DynamicFieldsModelSerializer):
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


class ProjectRelatedSerializer(DynamicFieldsRelatedSerializer):
    class Meta(object):
        model_class = Project
        model_serializer_class = ProjectSerializer

