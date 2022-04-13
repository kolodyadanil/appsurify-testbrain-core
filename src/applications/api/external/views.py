# -*- coding: utf-8 -*-

import json
import re
import urllib
import urllib.parse
from django.db import models
from django.db.models import F, Value, CharField
from django.db.models.functions import Concat
from django.http import HttpRequest
from django.utils.translation import ugettext_lazy as _
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import *
from rest_framework.response import Response

from applications.api.common.views import MultiSerializerViewSetMixin
from applications.api.report.views import TestReportModelViewSet
from applications.testing.models import Test, Defect, TestRunResult, TestRun
# from applications.license.utils import check_usage
from applications.organization.models import Organization
from applications.organization.utils import get_current_organization
from applications.vcs.models import Branch

from applications.testing.selectors import Priority, prioritized_test_list

from .permissions import IsAuthenticatedToken
from .serializers import *
from .utils import ConfirmationHMAC

## TODO: THIS IS DEPRICATED FLAGS
PRIORITY_HIGH = 1
PRIORITY_MEDIUM = 2
PRIORITY_LOW = 3
PRIORITY_UNASSIGNED = 4
PRIORITY_RERUN = 5
PRIORITY_READY_DEFECT = 6
PRIORITY_OPEN_DEFECT = 7
PRIORITY_TOP20 = 8
PRIORITY_PERCENT = 9
PRIORITY_FOR_TEST = 10
PRIORITY_FOR_TEST_WITH_DAY = 11
PRIORITY_EXECUTION_TIME_UNDER = 12


class ExternalAPIViewSet(MultiSerializerViewSetMixin, viewsets.GenericViewSet):
    permission_classes = (IsAuthenticatedToken,)
    queryset = Commit.objects.all()

    queryset_action = {
        'commit_risk_view': Commit.objects.all(),
        'prioritized_tests_view': Test.objects.all(),
        'output_test_run_view': TestRun.objects.all(),
    }

    serializer_class = None
    serializer_action_classes = {
        'import_view': ImportReportSerializer,
        'prioritized_tests_view': PrioritizedTestsSerializer,
        'output_test_run_view': OutputTestSuiteSerializer,
    }

    # filter_class = None
    # filter_action_classes = {}
    # ordering_fields = ()
    # search_fields = ()
    # filter_fields = ()

    def get_queryset(self):
        queryset = super(ExternalAPIViewSet, self).get_queryset()
        token = self.request.META.get('HTTP_TOKEN', None)
        if token:
            organization = ConfirmationHMAC.from_key(token)
            queryset = queryset.filter(project__organization=organization)
        else:
            queryset = queryset.none()
        return queryset

    @action(methods=['POST', ], detail=False, url_path=r'import')
    def import_view(self, request, *args, **kwargs):
        try:
            serializer = ImportReportSerializer(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)

            report = serializer.save(self.request)

            if report.get('error', None):
                return Response(data={'detail': [_('{}'.format(report.get('error')))]},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            if report is False:
                return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            report_serializer = OutputImportSerializer(data=report, many=False)
            report_serializer.is_valid(raise_exception=True)

            return Response(data=report_serializer.data, status=status.HTTP_201_CREATED)

        except Organization.DoesNotExist:
            raise APIException("Organization matching query does not exist.")
        except Project.DoesNotExist:
            raise APIException("Project matching query does not exist.")
        except TestRun.DoesNotExist:
            raise APIException("TestRun matching query does not exist.")
        except TestSuite.DoesNotExist:
            raise APIException("TestSuite matching query does not exist.")
        except Commit.DoesNotExist:
            raise APIException("Commit matching query does not exist.")
        # except Exception as e:
        #     raise APIException(e)

    class ParamsPrioritizationTestSerializer(serializers.Serializer):
        name_type = serializers.CharField(required=True)

        project = serializers.IntegerField(required=False)
        project_name = serializers.CharField(required=False)

        test_suite = serializers.IntegerField(required=False)
        test_suite_name = serializers.CharField(required=False)

        target_branch = serializers.CharField(required=False)
        target_branch_id = serializers.IntegerField(required=False)

        commit_type = serializers.CharField(required=True)
        commit = serializers.CharField(required=False)
        from_commit = serializers.CharField(required=False)

        priority = serializers.IntegerField(required=True)
        percent = serializers.IntegerField(required=False, allow_null=True, default=None)

        classname = serializers.BooleanField(required=True)
        classname_separator = serializers.CharField(required=False, default="")

        testsuitename = serializers.BooleanField(required=True)
        testsuitename_separator = serializers.CharField(required=False, default="")

        day = serializers.CharField(required=False)
        time = serializers.CharField(required=False)

        organization = serializers.ReadOnlyField()

        def _get_request(self):
            request = self.context.get('request')
            if not isinstance(request, HttpRequest):
                request = request._request
            return request

        def _validate_project(self, attrs):
            project = attrs.pop("project", "")
            project_name = attrs.pop("project_name", "")

            if not project and not project_name:
                raise serializers.ValidationError("Require set project or project_name")
            elif project and project_name:
                raise serializers.ValidationError("Set only one project or project_name")

            try:
                if project:
                    attrs["project"] = Project.objects.get(organization=attrs["organization"], id=project)
                if project_name:
                    attrs["project"] = Project.objects.get(organization=attrs["organization"],
                                                           name__iexact=project_name)
            except Project.DoesNotExist:
                raise serializers.ValidationError("Project not found")

            return attrs["project"]

        def _validate_commit(self, attrs):
            commit = attrs.pop("commit", "")
            if not commit:
                raise serializers.ValidationError("Require set commit")
            try:
                attrs["commit"] = Commit.objects.get(project=attrs["project"], sha=commit)
            except Commit.DoesNotExist:
                raise serializers.ValidationError("Commit not found")
            return attrs["commit"]

        def _validate_from_commit(self, attrs):
            commit = attrs.pop("from_commit", "")
            if commit:
                try:
                    attrs["from_commit"] = Commit.objects.get(project=attrs["project"], sha=commit)
                except Commit.DoesNotExist:
                    raise serializers.ValidationError("Commit not found")
            else:
                if not attrs["commit"]:
                    raise serializers.ValidationError("Require set from_commit")
                attrs["from_commit"] = attrs["commit"]
            return attrs["from_commit"]

        def _validate_test_suite(self, attrs):
            test_suite = attrs.pop("test_suite", "")
            test_suite_name = attrs.pop("test_suite_name", "")

            if not test_suite and not test_suite_name:
                raise serializers.ValidationError("Require set test_suite or test_suite_name")
            elif test_suite and test_suite_name:
                raise serializers.ValidationError("Set only one test_suite or test_suite_name")

            try:
                if test_suite:
                    attrs["test_suite"] = TestSuite.objects.get(project=attrs["project"], id=test_suite)
                if test_suite_name:
                    attrs["test_suite"] = TestSuite.objects.get(project=attrs["project"], name__iexact=test_suite_name)
            except Project.DoesNotExist:
                raise serializers.ValidationError("TestSuite not found")

            return attrs["test_suite"]

        def _validate_target_branch(self, attrs):
            target_branch = attrs.pop("target_branch", "")
            target_branch_id = attrs.pop("target_branch_id", "")

            if not target_branch and not target_branch_id:
                raise serializers.ValidationError("Require set target_branch or target_branch_id")
            elif target_branch and target_branch_id:
                raise serializers.ValidationError("Set only one target_branch or target_branch_id")

            try:
                if target_branch:
                    attrs["target_branch"] = Branch.objects.get(project=attrs["project"], name__iexact=target_branch)
                if target_branch_id:
                    attrs["target_branch"] = TestSuite.objects.get(project=attrs["project"], id=target_branch_id)
            except Project.DoesNotExist:
                raise serializers.ValidationError("Branch not found")

            return attrs["target_branch"]

        def validate(self, attrs):

            attrs["organization"] = get_current_organization(self._get_request())
            attrs["project"] = self._validate_project(attrs)
            attrs["commit"] = self._validate_commit(attrs)
            attrs["from_commit"] = self._validate_from_commit(attrs)
            attrs["target_branch"] = self._validate_target_branch(attrs)
            attrs["test_suite"] = self._validate_test_suite(attrs)

            if attrs["priority"] in [Priority.TOP20, Priority.PERCENT]:
                percent = attrs["percent"]
                if not percent or percent == 0:
                    raise serializers.ValidationError("Please define 'percent'")

            return attrs

    @action(methods=['GET', ], detail=False, url_path=r"prioritized-tests")  # TODO: rename url path
    def prioritized_tests_view(self, request, *args, **kwargs):
        # get base queryset
        kwargs['context'] = self.get_serializer_context()
        params_serializer = self.ParamsPrioritizationTestSerializer(data=request.query_params, **kwargs)
        params_serializer.is_valid(raise_exception=True)
        params = params_serializer.validated_data

        queryset = prioritized_test_list(params=params)

        serializer = PrioritizedTestsSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['GET', ], detail=False, url_path=r'output')  # TODO: rename url path
    def output_test_run_view(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        result = {}
        if 'test_run' not in request.query_params:
            raise APIException("TestRun matching query does not exist.")

        if request and 'test_run' in request.query_params:
            test_run = request.query_params.get('test_run')
            if not test_run.isdigit():
                test_run = queryset.get(name=test_run)
            else:
                test_run = queryset.get(id=test_run)

            result['new_defects'] = test_run.created_defects.exclude(original_defect__isnull=False).exclude(
                type=Defect.TYPE_FLAKY).count()

            result['flaky_defects'] = test_run.founded_defects.filter(type=Defect.TYPE_FLAKY).count()

            result['reopened_defects'] = test_run.reopened_defects.exclude(type=Defect.TYPE_FLAKY).count()

            result['reopened_flaky_defects'] = test_run.reopened_defects.filter(
                type=Defect.TYPE_FLAKY).count()

            result['flaky_failures_breaks'] = test_run.test_run_results.filter(
                models.Q(status=TestRunResult.STATUS_FAIL) | models.Q(status=TestRunResult.STATUS_BROKEN)).filter(
                models.Q(founded_defects__type=Defect.TYPE_FLAKY) & ~models.Q(
                    founded_defects__status=Defect.STATUS_CLOSED)).count()

            result['failed_test'] = test_run.test_run_results.filter(status=TestRunResult.STATUS_FAIL).exclude(
                created_defects__type=Defect.TYPE_FLAKY).count()

            result['broken_test'] = test_run.test_run_results.filter(status=TestRunResult.STATUS_BROKEN).exclude(
                created_defects__type=Defect.TYPE_FLAKY).count()

            result['passed_test'] = test_run.test_run_results.filter(status=TestRunResult.STATUS_PASS).exclude(
                created_defects__type=Defect.TYPE_FLAKY).count()

            result['skipped_test'] = test_run.test_run_results.filter(status=TestRunResult.STATUS_SKIPPED).exclude(
                created_defects__type=Defect.TYPE_FLAKY).count()

            serializer = OutputTestSuiteSerializer(result)

            return Response(serializer.data)

        else:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(methods=['GET', ], detail=False, url_path=r'commit-risk')
    def commit_riskiness_view(self, request, *args, **kwargs):
        """
        project -- project id, put this field into query
        commit -- commit sha, put this field into query
        """
        # if not request or 'project' not in request.query_params or 'commit' not in request.query_params:
        #     return Response(status=status.HTTP_400_BAD_REQUEST)
        if 'project' not in request.query_params and 'project_name' not in request.query_params:
            raise APIException('Define witch one `project` or `project_name`')

        if 'commit' not in request.query_params:
            raise APIException('Define commit sha.')

        project_params = {}

        project_id = request.query_params.get('project', None)
        if project_id:
            project_params['id'] = project_id

        project_name = request.query_params.get('project_name', None)
        if project_name:
            project_params['name'] = project_name

        try:
            project = Project.objects.get(**project_params)
        except Project.DoesNotExist:
            raise APIException('Project not found.')

        commit = request.query_params.get('commit')
        commit = Commit.objects.filter(sha=commit, project=project).last()

        if not commit:
            return Response(status=status.HTTP_404_NOT_FOUND)

        riskiness = commit.riskiness

        if riskiness <= 0.25:
            color = 'green'
            level = 3
        elif 0.25 < riskiness <= 0.5:
            color = 'orange'
            level = 2
        else:
            color = 'red'
            level = 1

        return Response({'color': color, 'level': level, 'riskiness': riskiness})
