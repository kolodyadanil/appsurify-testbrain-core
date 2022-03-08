# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from urllib.parse import urlunsplit

from rest_framework import serializers

from applications.api.external.utils import ConfirmationHMAC
from applications.api.project.serializers import ProjectRelatedSerializer
from applications.api.testing.serializers import TestSuiteRelatedSerializer
from applications.organization.utils import get_current_organization
from applications.project.models import Project
from applications.testing.models import TestSuite
from applications.testing.tools import SpecFlow
from applications.vcs.models import Commit


class CommitRiskSerializer(serializers.Serializer):
    project_id = serializers.IntegerField(min_value=0, required=False)
    project_name = serializers.CharField(max_length=255, allow_blank=True)
    test_suite_id = serializers.IntegerField(min_value=0, required=True)
    commit_id = serializers.IntegerField(min_value=0, required=False)
    commit_name = serializers.CharField(max_length=255)


class ImportReportSerializer(serializers.Serializer):

    def _validate_project(self, project_id=None, project_name=None):
        params = {}
        if project_id:
            params['id'] = project_id
        if project_name:
            params['name'] = project_name

        organization = get_current_organization(self.context['request'])
        params['organization'] = organization
        project = Project.objects.get(**params)

        return project

    def _validate_test_suite(self, project, test_suite_id=None, test_suite_name=None):
        params = {}

        if test_suite_id:
            params['id'] = test_suite_id
        if test_suite_name:
            params['name'] = test_suite_name

        try:
            test_suite = TestSuite.objects.get(project=project, **params)
        except TestSuite.MultipleObjectsReturned:
            test_suite = TestSuite.objects.filter(project=project, **params).last()

        return test_suite

    def validate(self, attrs):
        project_id = self.initial_data.get('project', None)
        project_name = self.initial_data.get('project_name', None)
        test_suite_id = self.initial_data.get('test_suite', None)
        test_suite_name = self.initial_data.get('test_suite_name', None)

        project = self._validate_project(project_id=project_id, project_name=project_name)
        test_suite = self._validate_test_suite(project, test_suite_id=test_suite_id, test_suite_name=test_suite_name)

        attrs['project'] = project
        attrs['test_suite'] = test_suite

        repo_type = attrs.get('repo', 'git')
        commit_sha = attrs.get('commit', None)

        if commit_sha is not None:

            if repo_type == 'perforce':

                if isinstance(commit_sha, (str, bytes)):

                    if not commit_sha.isdigit():
                        raise serializers.ValidationError(
                            {'commit': "Commit `{commmit_sha}` incorrect because choice repo 'perforce'"
                             "".format(commmit_sha=commit_sha)})

                    commit_sha = int(commit_sha)

                    try:
                        commit_sha = Commit.objects.get(
                            project=project, message__iregex="\[git-p4.*change\s=\s{:d}\]".format(commit_sha))
                        commit_sha = commit_sha.sha
                    except Commit.DoesNotExist:
                        commit_sha = None

        attrs['commit'] = self._validate_commit(commit_sha)
        return attrs

    def _validate_commit(self, commit_sha):
        if commit_sha.rfind(';') != -1:
            commit_sha = commit_sha[:commit_sha.rfind(';')]
        return commit_sha

    def save(self, request):
        token = request.META.get('HTTP_TOKEN', None)
        organization = ConfirmationHMAC.from_key(token)

        validated_data = self.validated_data

        project = validated_data['project']
        test_suite = validated_data['test_suite']

        commit_sha = validated_data.get('commit', None)
        file = validated_data['file']
        type = validated_data['type']
        test_run_name = validated_data.get('test_run_name', None)
        try:
            commit = Commit.objects.get(project_id=project, sha=commit_sha)
        except (Commit.DoesNotExist, Commit.MultipleObjectsReturned) as e:
            return {'error': 'XMLError: {}'.format(e)}
        utils = SpecFlow.ImportUtils(
            type_xml=type,
            file_obj=file,
            data=dict(project=project, test_suite=test_suite, commit=commit),
            user_id=organization.owner.organization_user.user.id,
            test_run_name=test_run_name,
            host=urlunsplit((request.scheme, request.get_host(), '/test-runs/', None, None))
        )
        result = utils.import_xml_tests()
        return result

    # project = ProjectRelatedSerializer(fields=('id', 'name'), queryset=Project.objects.all(), many=False, required=False)
    repo = serializers.CharField(write_only=True, required=False, default='git')

    project = ProjectRelatedSerializer(fields=('id', 'name'), required=False, read_only=True)
    project_name = serializers.CharField(write_only=True, required=False)

    test_suite = TestSuiteRelatedSerializer(fields=('id', 'name'), required=False, read_only=True)
    test_suite_name = serializers.CharField(write_only=True, required=False)

    commit = serializers.CharField(max_length=255, required=False)
    type = serializers.ChoiceField(choices=SpecFlow.ALLOWED_FORMAT_TYPES, required=True)
    test_run_name = serializers.CharField(max_length=255, allow_blank=True, allow_null=True, required=False)
    file = serializers.FileField(required=True)


class OutputImportSerializer(serializers.Serializer):
    new_defects = serializers.IntegerField(default=0)
    flaky_defects = serializers.IntegerField(default=0)
    reopened_defects = serializers.IntegerField(default=0)
    reopened_flaky_defects = serializers.IntegerField(default=0)
    flaky_failures_breaks = serializers.IntegerField(default=0)

    failed_tests = serializers.IntegerField(default=0)
    broken_tests = serializers.IntegerField(default=0)
    skipped_tests = serializers.IntegerField(default=0)
    passed_tests = serializers.IntegerField(default=0)

    test_run_id = serializers.IntegerField(default=0)

    report_url = serializers.CharField(default=str())


class PrioritizedTestsSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=4096)


class OutputTestSuiteSerializer(serializers.Serializer):
    new_defects = serializers.IntegerField(default=0)
    flaky_defects = serializers.IntegerField(default=0)
    reopened_defects = serializers.IntegerField(default=0)
    reopened_flaky_defects = serializers.IntegerField(default=0)
    flaky_failures_breaks = serializers.IntegerField(default=0)

    failed_test = serializers.IntegerField(default=0)
    broken_test = serializers.IntegerField(default=0)
    passed_test = serializers.IntegerField(default=0)
    skipped_test = serializers.IntegerField(default=0)
