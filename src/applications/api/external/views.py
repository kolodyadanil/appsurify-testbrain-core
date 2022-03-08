# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import re
import urllib
import urllib.parse
from django.db import models
from django.db.models import F, Value, CharField
from django.db.models.functions import Concat
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

from .permissions import IsAuthenticatedToken
from .serializers import *
from .utils import ConfirmationHMAC

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

    @action(methods=['GET', ], detail=False, url_path=r'prioritized-tests')  # TODO: rename url path
    def prioritized_tests_view(self, request, *args, **kwargs):
        # get base queryset
        queryset = self.get_queryset()

        # change request object properties. set mutable
        if not request.GET._mutable:
            request.GET._mutable = True

        repo_type = request.query_params.get('repo', 'git')  # Maybe 'perforce'
        # _re_p4 = re.compile(r"\[git-p4.*depot-paths\s=\s\"(?P<target_branch>.*)\".*change\s=\s(?P<commit>\d+)\]")

        # validate project_* params in request query params
        project_params = {}

        if 'project' not in request.query_params and 'project_name' not in request.query_params:
            raise APIException('Define witch one `project` or `project_name`')

        project_id = request.query_params.get('project', None)
        if project_id:
            project_params['id'] = int(project_id)

        project_name = request.query_params.get('project_name', None)
        if project_name:
            project_params['name'] = str(project_name)

        try:
            project = Project.objects.get(**project_params)
        except Project.DoesNotExist:
            raise APIException('Project not found.')
        except Exception as e:
            raise APIException(e)

        # normalize project filter param
        request.query_params['project'] = project.id

        # TEST_SUITE
        # validate test_suite_* params in request query params
        if 'test_suite' in request.query_params or 'test_suite_name' in request.query_params:
            test_suite_params = {}

            test_suite_id = request.query_params.get('test_suite', None)
            if test_suite_id:
                test_suite_params['id'] = int(test_suite_id)

            test_suite_name = request.query_params.get('test_suite_name', None)
            if test_suite_name:
                test_suite_params['name'] = test_suite_name

            try:
                test_suite = TestSuite.objects.get(project=project, **test_suite_params)
            except TestSuite.DoesNotExist:
                raise APIException('TestSuite not found.')

            # normalize test_suite filter param
            request.query_params['test_suite'] = test_suite.id

            organization = get_current_organization(request=request)
            # pay_flag = check_usage(organization=organization, test_suite_id=test_suite.id)
            # if pay_flag:
            #     raise APIException('Number of minutes has been met for the month.')

        # COMMITS
        # validate commit params in request query params
        for arg in ('commit', 'from_commit'):
            if request and arg in request.query_params:
                commit_sha = request.query_params.get(arg)

                try:
                    commit_sha = urllib.parse.unquote_plus(commit_sha)
                except Exception:
                    pass

                try:
                    if repo_type == 'perforce':
                        if isinstance(commit_sha, (str, bytes)):
                            if not commit_sha.isdigit():
                                raise APIException("Incorrect params 'commit' {commit_sha} "
                                                   "with param 'repo' = 'perforce'".format(commit_sha=commit_sha))

                        commit_sha = int(commit_sha)
                        commit_arg = Commit.objects.get(
                            project=project, message__iregex="\[git-p4.*change\s=\s{:d}\]".format(commit_sha))

                    elif repo_type != 'perforce' and commit_sha.find(';') != -1:
                        commit_sha = commit_sha[:commit_sha.rfind(';')]
                        commit_arg = Commit.objects.get(project=project, sha=commit_sha)

                    else:
                        commit_arg = Commit.objects.get(project=project, sha=commit_sha)

                    request.query_params[arg] = commit_arg.id

                except Commit.DoesNotExist:
                    raise APIException("Commit from '{0}' param not found.".format(arg))
                except Commit.MultipleObjectsReturned:
                    raise APIException('Founded duplicated commits. Please contact with support.')

        # TARGET_BRANCH
        if 'target_branch' in request.query_params or 'target_branch_id' in request.query_params:
            if repo_type == 'perforce':
                target_branch_id = request.query_params.get('target_branch_id', None)
                if target_branch_id:
                    raise APIException("Incompatible 'target_branch_id' param with 'repo' = 'perforce'. "
                                       "Use only 'target_branch'")
                target_branch_name = request.query_params.get('target_branch', None)
                if target_branch_name:
                    try:
                        target_branch = Branch.objects.filter(
                            project=project,
                            commits__message__regex="\[git-p4.*depot-paths\s=\s\"{target_branch_name}\".*\]".format(
                                target_branch_name=target_branch_name
                            )
                        ).first()
                        if target_branch is None:
                            raise APIException('Target branch not found.')
                    except Exception:
                        raise APIException('Target branch not found.')
                    # normalize target_branch filter param
                    request.query_params['target_branch'] = target_branch.id
            else:
                target_branch_params = {}
                target_branch_id = request.query_params.get('target_branch_id', None)
                if target_branch_id:
                    target_branch_params['id'] = int(target_branch_id)
                target_branch_name = request.query_params.get('target_branch', None)
                if target_branch_name:
                    target_branch_params['name'] = target_branch_name
                try:
                    target_branch = Branch.objects.get(project=project, **target_branch_params)
                    target_branch_name = target_branch.name
                except Branch.DoesNotExist:
                    raise APIException('Target branch not found.')

                # normalize target_branch filter param
                request.query_params['target_branch'] = target_branch.id

        # PRIORITY
        # validate priority params in request query params
        if 'priority' not in request.query_params:
            raise APIException('`priority` is required.')

        priority = int(request.query_params.get('priority', 0))

        test_view = TestReportModelViewSet(request=request)
        filtered_queryset = test_view.get_queryset()
        try:
            if priority == PRIORITY_HIGH:
                queryset = test_view.get_high_queryset(queryset=filtered_queryset)
            elif priority == PRIORITY_MEDIUM:
                queryset = test_view.get_medium_queryset(queryset=filtered_queryset)
            elif priority == PRIORITY_LOW:
                queryset = test_view.get_low_queryset(queryset=filtered_queryset)
            elif priority == PRIORITY_UNASSIGNED:
                queryset = test_view.get_unassigned_queryset(queryset=filtered_queryset)
            elif priority == PRIORITY_READY_DEFECT:
                queryset = test_view.get_ready_defect_queryset(queryset=filtered_queryset)
            elif priority == PRIORITY_OPEN_DEFECT:
                queryset = test_view.get_open_defect_queryset(queryset=filtered_queryset)
            elif priority == PRIORITY_RERUN:
                queryset = test_view.get_rerun_queryset(queryset=filtered_queryset)
            elif priority == PRIORITY_TOP20:
                queryset = test_view.get_top20_queryset(queryset=filtered_queryset)
            elif priority == PRIORITY_PERCENT:
                queryset = test_view.get_top_by_percent_queryset(queryset=filtered_queryset)
            elif priority == PRIORITY_FOR_TEST or priority == PRIORITY_FOR_TEST_WITH_DAY:
                queryset = test_view.get_all_queryset(queryset=filtered_queryset)
            else:
                raise APIException('Please choice priority from 1 to 11.')
        except NotFound:
            raise APIException(
                "No one commit in branch '{0}' has not associated test runs in specified test suite '{1}'".format(
                    target_branch_name, test_suite.name
                )
            )

        # OUTPUT NAME FORMAT
        classname = False
        testsuitename = False

        classname_separator = ""
        testsuitename_separator = ""

        if 'classname' in request.query_params:
            classname = request.query_params.get('classname', False)
            classname = json.loads(str(classname).lower())
            if not isinstance(classname, bool):
                raise APIException('Please choice `classname` only True/False.')

        if 'testsuitename' in request.query_params:
            testsuitename = request.query_params.get('testsuitename', False)
            testsuitename = json.loads(str(testsuitename).lower())
            if not isinstance(testsuitename, bool):
                raise APIException('Please choice `testsuitename` only True/False.')

        if classname:
            classname_separator = request.query_params.get("classname_separator", "")

        if testsuitename:
            testsuitename_separator = request.query_params.get("testsuitename_separator", "")

        queryset = queryset.values('name')

        if classname:
            queryset = (
                queryset.annotate(mname=F('name')).values('mname').annotate(name=Concat(
                    F('class_name'), Value(classname_separator), 'mname', output_field=CharField())).values('name')
            )
        if testsuitename:  # TODO: Remember this testsuite__name eq area__name
            queryset = (
                queryset.annotate(mname=F('name')).values('mname').annotate(name=Concat(
                    F('area__name'), Value(testsuitename_separator), 'mname', output_field=CharField())).values('name')
            )

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
