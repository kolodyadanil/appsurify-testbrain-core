# -*- coding: utf-8 -*-
import re
import operator
import collections
import pytz
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.db.models import Count
from django.db.models.expressions import *
from django.http import Http404
from django.shortcuts import get_object_or_404 as _get_object_or_404
from rest_framework import permissions
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.exceptions import *
from rest_framework.response import Response
from datetime import timedelta, date

from applications.api.common.views import MultiSerializerViewSetMixin
from applications.project.permissions import IsOwnerOrReadOnly
from applications.vcs.utils.analysis import calculate_user_analysis, calculate_user_analysis_by_range, avg_per_range, calculate_similar_by_commit
from applications.vcs.utils.bugspots import Bugspots
from .filters import *
from .serializers import *

from applications.ml.neural_network import MLPredictor


def get_object_or_404(queryset, *filter_args, **filter_kwargs):
    """
    Same as Django's standard shortcut, but make sure to also raise 404
    if the filter_kwargs don't match the required types.
    """
    try:
        return _get_object_or_404(queryset, *filter_args, **filter_kwargs)
    except (TypeError, ValueError):
        raise Http404


class ArraySubquery(models.Subquery):
    template = 'ARRAY(%(subquery)s)'


class ProjectReportModelViewSet(MultiSerializerViewSetMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Project API endpoints
    """
    model = Project

    queryset = Project.objects.all()
    queryset_action = {
        'list': Project.objects.all(),
    }

    serializer_class = ProjectReportSerializer
    serializer_action_classes = {
        'list': ProjectReportSerializer,
        'graph_add_commits': ProjectAddCommitGraphSerializer,
    }

    filter_class = ProjectReportFilterSet
    filter_action_classes = {}

    permission_classes = (permissions.IsAuthenticated, IsOwnerOrReadOnly,)

    ordering_fields = ()
    search_fields = ()
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'project_pk'

    def get_queryset(self):
        queryset = super(ProjectReportModelViewSet, self).get_queryset()
        user = self.request.user
        if user.is_superuser:
            return queryset

        organization = get_current_organization(request=self.request)
        if organization:
            queryset = queryset.filter(organization=organization)
            if not organization.is_admin(user):
                queryset = queryset.get_for_user(user)
        return queryset

    @action(methods=['GET', ], detail=False, url_path=r'(?P<project_pk>[0-9]+)/graph/commits/add')
    def graph_add_commits(self, request, project_pk=None, *args, **kwargs):
        queryset = Commit.objects.filter(project_id=project_pk)
        queryset = queryset.values('timestamp').annotate(
            ts=functions.TruncDay(models.F('timestamp')),
        ).values('ts').annotate(
            __count=models.Count('*')
        ).values('ts', '__count')

        serializer = ProjectAddCommitGraphSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AreaReportModelViewSet(MultiSerializerViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Area API endpoint
    ---
    list:
        List areas endpoint


    create:
        Create area endpoint


    retrieve:
        Retrieve area endpoint


    partial_update:
        Partial update area endpoint


    update:
        Update area endpoint


    """
    model = TestRunResult
    queryset = TestRunResult.objects.all()
    queryset_action = {
        'list': TestRunResult.objects.all(),
    }

    serializer_class = AreaReportSerializer
    serializer_action_classes = {
        'list': AreaReportSerializer,
    }

    filter_class = AreaReportFilterSet
    filter_action_classes = {
        'list': AreaReportFilterSet,
    }

    search_fields = ()
    ordering_fields = ()
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'area_pk'

    def get_queryset(self):
        queryset = super(AreaReportModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        test_ids = list(queryset.values_list('test_id', flat=True))
        area_ids = list(queryset.values_list('area_id', flat=True))
        queryset_subquery = (queryset.filter(test_id=models.OuterRef('id')).order_by('-created'))
        queryset_tests_subquery = (
            Test.objects.filter(id__in=test_ids).filter(area_id=OuterRef('id')).values('area_id').order_by().annotate(
                __count=functions.Coalesce(models.Count('*'), 0)).values('__count')[:1])
        queryset_passed_tests_subquery = (Test.objects.filter(id__in=test_ids).annotate(
            current_status=models.Subquery(queryset_subquery.values('status')[:1],
                                           output_field=models.CharField())).filter(area_id=OuterRef('id')).values(
            'area_id').order_by().filter(current_status=TestRunResult.STATUS_PASS).annotate(
            __count=functions.Coalesce(models.Count('*'), 0)).values('__count')[:1])
        queryset_failed_tests_subquery = (Test.objects.filter(id__in=test_ids).annotate(
            current_status=models.Subquery(queryset_subquery.values('status')[:1],
                                           output_field=models.CharField())).filter(area_id=OuterRef('id')).values(
            'area_id').order_by().filter(current_status=TestRunResult.STATUS_FAIL).annotate(
            __count=functions.Coalesce(models.Count('*'), 0)).values('__count')[:1])
        queryset_broken_tests_subquery = (Test.objects.filter(id__in=test_ids).annotate(
            current_status=models.Subquery(queryset_subquery.values('status')[:1],
                                           output_field=models.CharField())).filter(area_id=OuterRef('id')).values(
            'area_id').order_by().filter(current_status=TestRunResult.STATUS_BROKEN).annotate(
            __count=functions.Coalesce(models.Count('*'), 0)).values('__count')[:1])
        queryset_not_run_tests_subquery = (Test.objects.filter(id__in=test_ids).annotate(
            current_status=models.Subquery(queryset_subquery.values('status')[:1],
                                           output_field=models.CharField())).filter(area_id=OuterRef('id')).values(
            'area_id').order_by().filter(current_status__in=[TestRunResult.STATUS_NOT_RUN, TestRunResult.STATUS_SKIPPED,
                                                             TestRunResult.STATUS_PENDING]).annotate(
            __count=functions.Coalesce(models.Count('*'), 0)).values('__count')[:1])
        queryset = Area.objects.filter(
            id__in=area_ids
        ).annotate(
            project_name=models.F('project__name'),
            tests__count=models.Subquery(queryset_tests_subquery, output_field=models.IntegerField()),
            passed_tests__count=models.Subquery(queryset_passed_tests_subquery, output_field=models.IntegerField()),
            failed_tests__count=models.Subquery(queryset_failed_tests_subquery, output_field=models.IntegerField()),
            broken_tests__count=models.Subquery(queryset_broken_tests_subquery, output_field=models.IntegerField()),
            not_run_tests__count=models.Subquery(queryset_not_run_tests_subquery, output_field=models.IntegerField()),
        ).values(
            'id',
            'name',
            'project_id',
            'project_name',
            'tests__count',
            'passed_tests__count',
            'failed_tests__count',
            'broken_tests__count',
            'not_run_tests__count',
        ).order_by('name')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['GET', ], detail=False, url_path=r'bugspots')
    def bugspots(self, request, *args, **kwargs):

        data = list()

        queryset = Commit.objects.all().order_by('timestamp')

        extra_filter = dict()

        if 'project' in request.query_params:
            project_id = request.query_params.get('project')
            extra_filter.update({
                'project_id': project_id,
                'project__organization': get_current_organization(self.request)
            })
        else:
            raise ValidationError('Project is required.')

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise ValidationError('Project not found.')

        queryset = queryset.filter(**extra_filter)

        if 'timestamp__range' in request.query_params:
            value = request.query_params.get('timestamp__range')
            from_date, end_date = map(int, value.split(','))
            from_date, end_date = timezone.datetime.fromtimestamp(from_date, tz=pytz.UTC).replace(hour=0, minute=0, second=0, microsecond=0), timezone.datetime.fromtimestamp(end_date, tz=pytz.UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timezone.timedelta(days=2)
            lookup_expr = LOOKUP_SEP.join(['timestamp', 'range'])
            extra_filter.update({lookup_expr: (from_date, end_date)})
        else:
            if queryset:
                end_date = queryset.last().timestamp
                from_date = end_date - timezone.timedelta(days=14)
                lookup_expr = LOOKUP_SEP.join(['timestamp', 'range'])
                extra_filter.update({lookup_expr: (from_date, end_date)})

        risk_queryset = queryset.filter(timestamp__lte=from_date).order_by('timestamp')

        queryset = queryset.filter(**extra_filter).order_by('timestamp')

        if queryset:
            b = Bugspots(project, risk_queryset)
            # hotspots = b.get_hotspots()
            red_hotspots = b.get_red_hotspots()
            orange_hotspots = b.get_orange_hotspots()
            green_hotspots = b.get_green_hotspots()

            areas_dict = dict()
            commits_dict = dict()

            for commit in queryset.values('display_id', 'message', 'author', 'timestamp', 'files__full_filename', 'areas__id', 'areas__name', 'riskiness'):

                if commit['display_id'] not in commits_dict:
                    commits_dict[commit['display_id']] = {
                        'display_id': commit['display_id'],
                        'message': commit['message'],
                        'author': commit['author'],
                        'timestamp': commit['timestamp'],
                        'areas': list(),
                        'riskiness': commit['riskiness'],
                        'code_hotspots': dict(red=list(), orange=list(), green=list()),
                        'files': list()
                    }

                if commit['areas__id'] not in set().union(*(d.keys() for d in commits_dict[commit['display_id']]['areas'])):
                    commits_dict[commit['display_id']]['areas'].append({commit['areas__id']: commit['areas__name']})

                filename = commit['files__full_filename']
                commits_dict[commit['display_id']]['files'].append(filename)

                if filename in [hotspot.filename for hotspot in red_hotspots]:
                    for hotspot in red_hotspots:
                        if hotspot.filename == filename:
                            commits_dict[commit['display_id']]['code_hotspots']['red'].append(
                                (hotspot.score, hotspot.filename))
                elif filename in [hotspot.filename for hotspot in orange_hotspots]:
                    for hotspot in orange_hotspots:
                        if hotspot.filename == filename:
                            commits_dict[commit['display_id']]['code_hotspots']['orange'].append(
                                (hotspot.score, hotspot.filename))
                elif filename in [hotspot.filename for hotspot in green_hotspots]:
                    for hotspot in green_hotspots:
                        if hotspot.filename == filename:
                            commits_dict[commit['display_id']]['code_hotspots']['green'].append(
                                (hotspot.score, hotspot.filename))
                else:
                    commits_dict[commit['display_id']]['code_hotspots']['green'].append((float(0.0), filename))

            for commit_display_id, commit_data in commits_dict.items():
                for area in commit_data['areas']:
                    for area_id, area_name in area.items():
                        if area_id not in areas_dict:
                            areas_dict[area_id] = {
                                'id': area_id,
                                'name': area_name,
                                'commits': list()
                            }
                # if commit_data['area_id'] not in areas_dict:
                #     areas_dict[commit_data['area_id']] = {
                #         'id': commit_data['area_id'],
                #         'name': commit_data['area_name'],
                #         'commits': list()
                #     }

                        areas_dict[area_id]['commits'].append(commit_data)

            for area, area_data in areas_dict.items():
                data.append(area_data)

        serializer = AreaBugspotReportSerializer(data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['GET', ], detail=False, url_path=r'group/flaky')
    def group_flaky_tests(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        area_ids = set(list(queryset.values_list('area_id', flat=True)))
        test_run_ids = set(list(queryset.values_list('test_run_id', flat=True)))
        test_ids = set(list(queryset.values_list('test_id', flat=True)))

        newest_test_run = TestRun.objects.filter(id__in=test_run_ids).order_by('-created').first()
        newest_current_test_run_results = queryset.filter(test_run=newest_test_run,
                                                          test=models.OuterRef('id')).order_by('-created')

        queryset_tests_subquery = (
            Test.objects.filter(id__in=test_ids).filter(area_id=OuterRef('id')).values('area_id').order_by().annotate(
                __count=models.Count('*')).values('__count')[:1])

        queryset_passed_tests_subquery = (
            Test
                .objects
                .filter(id__in=test_ids)
                .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
                .filter(
                area_id=OuterRef('id')
            )
                .values('area_id')
                .order_by()
                .filter(
                models.Q(current_test_run_results_status=TestRunResult.STATUS_PASS) &
                models.Q(associated_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]) &
                models.Q(associated_defects__created_by_test_run=newest_test_run)
            )
                .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset_failed_tests_subquery = (
            Test
                .objects
                .filter(id__in=test_ids)
                .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
                .filter(
                area_id=OuterRef('id')
            )
                .values('area_id')
                .order_by()
                .filter(
                models.Q(
                    models.Q(current_test_run_results_status=TestRunResult.STATUS_FAIL) &
                    models.Q(associated_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]) &
                    models.Q(associated_defects__created_by_test_run=newest_test_run)
                )
                | models.Q(
                    models.Q(associated_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]) &
                    models.Q(associated_defects__created_by_test_run=newest_test_run.previous_test_run) &
                    models.Q(current_test_run_results_status=TestRunResult.STATUS_FAIL)
                )
            )
                .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset_broken_tests_subquery = (
            Test
                .objects
                .filter(id__in=test_ids)
                .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
                .filter(
                area_id=OuterRef('id')
            )
                .values('area_id')
                .order_by()
                .filter(
                models.Q(current_test_run_results_status=TestRunResult.STATUS_BROKEN) &
                models.Q(associated_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]) &
                models.Q(associated_defects__created_by_test_run=newest_test_run)
            )
                .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset_not_run_tests_subquery = (
            Test
                .objects
                .filter(id__in=test_ids)
                .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
                .filter(
                area_id=OuterRef('id')
            )
                .values('area_id')
                .order_by()
                .filter(
                models.Q(
                    current_test_run_results_status__in=[TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN,
                                                         TestRunResult.STATUS_SKIPPED]) &
                models.Q(associated_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]) &
                models.Q(associated_defects__created_by_test_run=newest_test_run)
            )
                .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset = Area.objects.filter(
            id__in=area_ids
        ).annotate(
            project_name=models.F('project__name'),
            tests__count=models.Subquery(queryset_tests_subquery, output_field=models.IntegerField()),

            passed_tests__count=models.Subquery(queryset_passed_tests_subquery, output_field=models.IntegerField()),
            failed_tests__count=models.Subquery(queryset_failed_tests_subquery, output_field=models.IntegerField()),
            broken_tests__count=models.Subquery(queryset_broken_tests_subquery, output_field=models.IntegerField()),
            not_run_tests__count=models.Subquery(queryset_not_run_tests_subquery, output_field=models.IntegerField()),

        ).values(
            'id',
            'name',
            'project_id',
            'project_name',
            'tests__count',
            'passed_tests__count',
            'failed_tests__count',
            'broken_tests__count',
            'not_run_tests__count',
        ).order_by('name')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['GET', ], detail=False, url_path=r'group/invalid')
    def group_invalid_tests(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        area_ids = set(list(queryset.values_list('area_id', flat=True)))
        test_run_ids = set(list(queryset.values_list('test_run_id', flat=True)))
        test_ids = set(list(queryset.values_list('test_id', flat=True)))

        newest_test_run = TestRun.objects.filter(id__in=test_run_ids).order_by('-created').first()
        newest_current_test_run_results = queryset.filter(test_run=newest_test_run,
                                                          test=models.OuterRef('id')).order_by('-created')

        queryset_tests_subquery = (
            Test.objects.filter(id__in=test_ids).filter(area_id=OuterRef('id')).values('area_id').order_by().annotate(
                __count=models.Count('*')).values('__count')[:1])

        queryset_passed_tests_subquery = (
            Test
                .objects
                .filter(id__in=test_ids)
                .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
                .filter(
                area_id=OuterRef('id')
            )
                .values('area_id')
                .order_by()
                .filter(
                models.Q(current_test_run_results_status=TestRunResult.STATUS_PASS) &
                models.Q(associated_defects__type=Defect.TYPE_INVALID_TEST) &
                ~models.Q(associated_defects__status=Defect.STATUS_CLOSED)
            )
                .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset_failed_tests_subquery = (
            Test
                .objects
                .filter(id__in=test_ids)
                .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
                .filter(
                area_id=OuterRef('id')
            )
                .values('area_id')
                .order_by()
                .filter(
                models.Q(current_test_run_results_status=TestRunResult.STATUS_FAIL) &
                models.Q(associated_defects__type=Defect.TYPE_INVALID_TEST) &
                ~models.Q(associated_defects__status=Defect.STATUS_CLOSED)
            )
                .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset_broken_tests_subquery = (
            Test
                .objects
                .filter(id__in=test_ids)
                .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
                .filter(
                area_id=OuterRef('id')
            )
                .values('area_id')
                .order_by()
                .filter(
                models.Q(current_test_run_results_status=TestRunResult.STATUS_BROKEN) &
                models.Q(associated_defects__type=Defect.TYPE_INVALID_TEST) &
                ~models.Q(associated_defects__status=Defect.STATUS_CLOSED)
            )
                .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset_not_run_tests_subquery = (
            Test
                .objects
                .filter(id__in=test_ids)
                .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
                .filter(
                area_id=OuterRef('id')
            )
                .values('area_id')
                .order_by()
                .filter(
                models.Q(
                    current_test_run_results_status__in=[TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN,
                                                         TestRunResult.STATUS_SKIPPED]) &
                models.Q(associated_defects__type=Defect.TYPE_INVALID_TEST) &
                ~models.Q(associated_defects__status=Defect.STATUS_CLOSED)
            )
                .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset = Area.objects.filter(
            id__in=area_ids
        ).annotate(
            project_name=models.F('project__name'),
            tests__count=models.Subquery(queryset_tests_subquery, output_field=models.IntegerField()),
            passed_tests__count=models.Subquery(queryset_passed_tests_subquery, output_field=models.IntegerField()),
            failed_tests__count=models.Subquery(queryset_failed_tests_subquery, output_field=models.IntegerField()),
            broken_tests__count=models.Subquery(queryset_broken_tests_subquery, output_field=models.IntegerField()),
            not_run_tests__count=models.Subquery(queryset_not_run_tests_subquery, output_field=models.IntegerField()),
        ).values(
            'id',
            'name',
            'project_id',
            'project_name',
            'tests__count',
            'passed_tests__count',
            'failed_tests__count',
            'broken_tests__count',
            'not_run_tests__count',
        ).order_by('name')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['GET', ], detail=False, url_path=r'group/open-defect')
    def group_open_defect_tests(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        area_ids = set(list(queryset.values_list('area_id', flat=True)))
        test_run_ids = set(list(queryset.values_list('test_run_id', flat=True)))
        test_ids = set(list(queryset.values_list('test_id', flat=True)))

        newest_test_run = TestRun.objects.filter(id__in=test_run_ids).order_by('-created').first()
        newest_current_test_run_results = queryset.filter(test_run=newest_test_run,
                                                          test=models.OuterRef('id')).order_by('-created')

        queryset_tests_subquery = (
            Test.objects.filter(id__in=test_ids).filter(area_id=OuterRef('id')).values('area_id').order_by().annotate(
                __count=models.Count('*')).values('__count')[:1])

        queryset_passed_tests_subquery = (
            Test
                .objects
                .filter(id__in=test_ids)
                .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
                .filter(
                area_id=OuterRef('id')
            )
                .values('area_id')
                .order_by()
                .filter(
                models.Q(current_test_run_results_status=TestRunResult.STATUS_PASS) &
                models.Q(associated_defects__type__in=[Defect.TYPE_PROJECT, Defect.TYPE_LOCAL]) &
                ~models.Q(associated_defects__status__in=[Defect.STATUS_NEW, Defect.STATUS_CLOSED, Defect.STATUS_READY])
            )
                .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset_failed_tests_subquery = (
            Test
                .objects
                .filter(id__in=test_ids)
                .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
                .filter(
                area_id=OuterRef('id')
            )
                .values('area_id')
                .order_by()
                .filter(
                models.Q(current_test_run_results_status=TestRunResult.STATUS_FAIL) &
                models.Q(associated_defects__type__in=[Defect.TYPE_PROJECT, Defect.TYPE_LOCAL]) &
                ~models.Q(
                    associated_defects__status__in=[Defect.STATUS_NEW, Defect.STATUS_CLOSED, Defect.STATUS_READY]))
                .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset_broken_tests_subquery = (
            Test
                .objects
                .filter(id__in=test_ids)
                .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
                .filter(
                area_id=OuterRef('id')
            )
                .values('area_id')
                .order_by()
                .filter(
                models.Q(current_test_run_results_status=TestRunResult.STATUS_BROKEN) &
                models.Q(associated_defects__type__in=[Defect.TYPE_PROJECT, Defect.TYPE_LOCAL]) &
                ~models.Q(
                    associated_defects__status__in=[Defect.STATUS_NEW, Defect.STATUS_CLOSED, Defect.STATUS_READY]))
                .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset_not_run_tests_subquery = (
            Test
                .objects
                .filter(id__in=test_ids)
                .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
                .filter(
                area_id=OuterRef('id')
            )
                .values('area_id')
                .order_by()
                .filter(
                models.Q(
                    current_test_run_results_status__in=[TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN,
                                                         TestRunResult.STATUS_SKIPPED]) &
                models.Q(associated_defects__type__in=[Defect.TYPE_PROJECT, Defect.TYPE_LOCAL]) &
                ~models.Q(
                    associated_defects__status__in=[Defect.STATUS_NEW, Defect.STATUS_CLOSED, Defect.STATUS_READY]))
                .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset = Area.objects.filter(
            id__in=area_ids
        ).annotate(
            project_name=models.F('project__name'),
            tests__count=models.Subquery(queryset_tests_subquery, output_field=models.IntegerField()),
            passed_tests__count=models.Subquery(queryset_passed_tests_subquery, output_field=models.IntegerField()),
            failed_tests__count=models.Subquery(queryset_failed_tests_subquery, output_field=models.IntegerField()),
            broken_tests__count=models.Subquery(queryset_broken_tests_subquery, output_field=models.IntegerField()),
            not_run_tests__count=models.Subquery(queryset_not_run_tests_subquery, output_field=models.IntegerField()),
        ).values(
            'id',
            'name',
            'project_id',
            'project_name',
            'tests__count',
            'passed_tests__count',
            'failed_tests__count',
            'broken_tests__count',
            'not_run_tests__count',
        ).order_by('name')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['GET', ], detail=False, url_path=r'group/ready-defect')
    def group_ready_defect_tests(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        area_ids = set(list(queryset.values_list('area_id', flat=True)))
        test_run_ids = set(list(queryset.values_list('test_run_id', flat=True)))
        test_ids = set(list(queryset.values_list('test_id', flat=True)))

        newest_test_run = TestRun.objects.filter(id__in=test_run_ids).order_by('-created').first()
        newest_current_test_run_results = queryset.filter(test_run=newest_test_run,
                                                          test=models.OuterRef('id')).order_by('-created')

        queryset_tests_subquery = (
            Test.objects.filter(id__in=test_ids).filter(area_id=OuterRef('id')).values('area_id').order_by().annotate(
                __count=models.Count('*')).values('__count')[:1])

        queryset_passed_tests_subquery = (
            Test
                .objects
                .filter(id__in=test_ids)
                .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
                .filter(
                area_id=OuterRef('id')
            )
                .values('area_id')
                .order_by()
                .filter(
                models.Q(current_test_run_results_status=TestRunResult.STATUS_PASS) &
                models.Q(associated_defects__type=Defect.TYPE_PROJECT) &
                models.Q(associated_defects__status=Defect.STATUS_READY)
            )
                .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset_failed_tests_subquery = (
            Test
                .objects
                .filter(id__in=test_ids)
                .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
                .filter(
                area_id=OuterRef('id')
            )
                .values('area_id')
                .order_by()
                .filter(
                models.Q(current_test_run_results_status=TestRunResult.STATUS_FAIL) &
                models.Q(associated_defects__type=Defect.TYPE_PROJECT) &
                models.Q(associated_defects__status=Defect.STATUS_READY)
            )
                .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset_broken_tests_subquery = (
            Test
                .objects
                .filter(id__in=test_ids)
                .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
                .filter(
                area_id=OuterRef('id')
            )
                .values('area_id')
                .order_by()
                .filter(
                models.Q(current_test_run_results_status=TestRunResult.STATUS_BROKEN) &
                models.Q(associated_defects__type=Defect.TYPE_PROJECT) &
                models.Q(associated_defects__status=Defect.STATUS_READY)
            )
                .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset_not_run_tests_subquery = (
            Test
                .objects
                .filter(id__in=test_ids)
                .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
                .filter(
                area_id=OuterRef('id')
            )
                .values('area_id')
                .order_by()
                .filter(
                models.Q(
                    current_test_run_results_status__in=[TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN,
                                                         TestRunResult.STATUS_SKIPPED]) &
                models.Q(associated_defects__type=Defect.TYPE_PROJECT) &
                models.Q(associated_defects__status=Defect.STATUS_READY)
            )
                .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset = Area.objects.filter(
            id__in=area_ids
        ).annotate(
            project_name=models.F('project__name'),
            tests__count=models.Subquery(queryset_tests_subquery, output_field=models.IntegerField()),
            passed_tests__count=models.Subquery(queryset_passed_tests_subquery, output_field=models.IntegerField()),
            failed_tests__count=models.Subquery(queryset_failed_tests_subquery, output_field=models.IntegerField()),
            broken_tests__count=models.Subquery(queryset_broken_tests_subquery, output_field=models.IntegerField()),
            not_run_tests__count=models.Subquery(queryset_not_run_tests_subquery, output_field=models.IntegerField()),
        ).values(
            'id',
            'name',
            'project_id',
            'project_name',
            'tests__count',
            'passed_tests__count',
            'failed_tests__count',
            'broken_tests__count',
            'not_run_tests__count',
        ).order_by('name')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['GET', ], detail=False, url_path=r'group/passed')
    def group_passed_tests(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        # print 'Queryset: ', queryset.count()

        area_ids = set(list(queryset.values_list('area_id', flat=True)))
        test_run_ids = set(list(queryset.values_list('test_run_id', flat=True)))
        test_ids = set(list(queryset.values_list('test_id', flat=True)))

        newest_test_run = TestRun.objects.filter(id__in=test_run_ids).order_by('-created').first()

        newest_current_test_run_results = queryset.filter(test_run=newest_test_run,
                                                          test=models.OuterRef('id')).order_by('-created')

        queryset_tests_subquery = (
            Test.objects.filter(id__in=test_ids).filter(area_id=OuterRef('id')).values('area_id').order_by().annotate(
                __count=models.Count('*')).values('__count')[:1])


        test_view_class = TestReportModelViewSet(request=request)
        group_queryset = test_view_class.filter_queryset(test_view_class.get_queryset())

        # print 'Group queryset: ', group_queryset.count()
        # for item in group_queryset:
        #     print '\t', item.name

        flaky_test_passed_test_run_result_queryset = set(list(
            test_view_class.get_group_flaky_tests_queryset(group_queryset).distinct().values_list('id', flat=True)))

        # print 'Flaky queryset: ', test_view_class.get_group_flaky_tests_queryset(group_queryset).distinct().count()
        # for item in test_view_class.get_group_flaky_tests_queryset(group_queryset).distinct():
        #     print '\t', item.name

        invalid_test_passed_test_run_result_queryset = set(list(
            test_view_class.get_group_invalid_tests_queryset(group_queryset).distinct().values_list('id', flat=True)))

        # print 'Invalid queryset: ', test_view_class.get_group_invalid_tests_queryset(group_queryset).distinct().count()
        # for item in test_view_class.get_group_invalid_tests_queryset(group_queryset).distinct():
        #     print '\t', item.name


        open_defect_test_passed_test_run_result_queryset = set(list(
            test_view_class.get_group_open_defect_tests_queryset(group_queryset).distinct().values_list('id', flat=True)))

        # print 'Open defect queryset: ', test_view_class.get_group_open_defect_tests_queryset(group_queryset).distinct().count()
        # for item in test_view_class.get_group_open_defect_tests_queryset(group_queryset).distinct():
        #     print '\t', item.name


        ready_defect_test_passed_test_run_result_queryset = set(list(
            test_view_class.get_group_ready_tests_queryset(group_queryset).distinct().values_list('id', flat=True)))

        # print 'Ready defect queryset: ', test_view_class.get_group_ready_tests_queryset(group_queryset).distinct().count()
        # for item in test_view_class.get_group_ready_tests_queryset(group_queryset).distinct():
        #     print '\t', item.name

        queryset_passed_tests_subquery = (
            Test
            .objects
            .filter(id__in=test_ids)
            .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
            .filter(
                area_id=OuterRef('id')
            )
            .values('area_id')
            .order_by()
            .exclude(
                models.Q(id__in=[id for id in flaky_test_passed_test_run_result_queryset]) |
                models.Q(id__in=[id for id in invalid_test_passed_test_run_result_queryset]) |
                models.Q(id__in=[id for id in open_defect_test_passed_test_run_result_queryset]) |
                models.Q(id__in=[id for id in ready_defect_test_passed_test_run_result_queryset])
            )
            .filter(
                models.Q(current_test_run_results_status=TestRunResult.STATUS_PASS)
            )
            .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset_failed_tests_subquery = (
            Test
            .objects
            .filter(id__in=test_ids)
            .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
            .filter(
                area_id=OuterRef('id')
            )
            .values('area_id')
            .order_by()
            .exclude(
                models.Q(id__in=[id for id in flaky_test_passed_test_run_result_queryset]) |
                models.Q(id__in=[id for id in invalid_test_passed_test_run_result_queryset]) |
                models.Q(id__in=[id for id in open_defect_test_passed_test_run_result_queryset]) |
                models.Q(id__in=[id for id in ready_defect_test_passed_test_run_result_queryset])
            )
            .filter(
                models.Q(current_test_run_results_status=TestRunResult.STATUS_FAIL)
            )
            .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset_broken_tests_subquery = (
            Test
            .objects
            .filter(id__in=test_ids)
            .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
            .filter(
                area_id=OuterRef('id')
            )
            .values('area_id')
            .order_by()
            .exclude(
                models.Q(id__in=[id for id in flaky_test_passed_test_run_result_queryset]) |
                models.Q(id__in=[id for id in invalid_test_passed_test_run_result_queryset]) |
                models.Q(id__in=[id for id in open_defect_test_passed_test_run_result_queryset]) |
                models.Q(id__in=[id for id in ready_defect_test_passed_test_run_result_queryset])
            )
            .filter(
                models.Q(current_test_run_results_status=TestRunResult.STATUS_BROKEN)
            )
            .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )

        queryset_not_run_tests_subquery = (
            Test
            .objects
            .filter(id__in=test_ids)
            .annotate(
                current_test_run_results_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            )
            .filter(
                area_id=OuterRef('id')
            )
            .values('area_id')
            .order_by()
            .exclude(
                models.Q(id__in=[id for id in flaky_test_passed_test_run_result_queryset]) |
                models.Q(id__in=[id for id in invalid_test_passed_test_run_result_queryset]) |
                models.Q(id__in=[id for id in open_defect_test_passed_test_run_result_queryset]) |
                models.Q(id__in=[id for id in ready_defect_test_passed_test_run_result_queryset])
            )
            .filter(
                models.Q(
                    current_test_run_results_status__in=[TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN,
                                                         TestRunResult.STATUS_SKIPPED])
            )
                .annotate(
                __count=models.Count('*')
            ).values('__count')[:1]
        )
        queryset = Area.objects.filter(
            id__in=area_ids
        ).annotate(
            project_name=models.F('project__name'),
            tests__count=models.Subquery(queryset_tests_subquery, output_field=models.IntegerField()),
            passed_tests__count=models.Subquery(queryset_passed_tests_subquery, output_field=models.IntegerField()),
            failed_tests__count=models.Subquery(queryset_failed_tests_subquery, output_field=models.IntegerField()),
            broken_tests__count=models.Subquery(queryset_broken_tests_subquery, output_field=models.IntegerField()),
            not_run_tests__count=models.Subquery(queryset_not_run_tests_subquery, output_field=models.IntegerField()),
        ).values(
            'id',
            'name',
            'project_id',
            'project_name',
            'tests__count',
            'passed_tests__count',
            'failed_tests__count',
            'broken_tests__count',
            'not_run_tests__count',
        ).order_by('name')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['GET', ], detail=False, url_path=r'chart/tests')
    def chart_by_test(self, request, *args, **kwargs):
        # queryset = self.filter_queryset(self.get_queryset())
        filter_expr = dict()
        if 'project' in request.query_params:
            value = request.query_params['project']
            lookup_expr = 'project'
            filter_expr = {lookup_expr: value}

        queryset = Area.objects.filter(**filter_expr).annotate(
            project_name=models.F('project__name')
        )

        queryset = queryset.values('id').annotate(
            __count=models.Count('tests', distinct=True
                                 ),
        ).filter(__count__gt=0).values('name', '__count')
        serializer = AreaByTestChartSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FileReportModelViewSet(MultiSerializerViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    File API endpoint
    ---
    list:
        List files endpoint


    create:
        Create file endpoint


    retrieve:
        Retrieve file endpoint


    partial_update:
        Partial update file endpoint


    update:
        Update file endpoint


    """
    model = File
    serializer_class = FileReportSerializer
    queryset = File.objects.filter(level=0).annotate(
        descendant_count=models.ExpressionWrapper(
            (
                    models.F('rght') - models.F('lft') - models.Value('1', output_field=models.IntegerField())
            ) / models.Value('2', output_field=models.IntegerField()), output_field=models.IntegerField())
    ).annotate(
        has_childs=models.Case(
            models.When(descendant_count__gt=0, then=True),
            default=False, output_field=models.BooleanField()
        )
    ).prefetch_related('areas')
    pagination_class = None

    ordering_fields = ()
    search_fields = ()

    filter_class = FileReportFilterSet
    filter_fields = ('project', 'area',)

    lookup_field = 'pk'
    lookup_url_kwarg = 'file_pk'

    def get_queryset(self):
        queryset = super(FileReportModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset

    def get_serializer(self, *args, **kwargs):
        """
        Return the serializer instance that should be used for validating and
        deserializing input, and for serializing output.
        """
        serializer_class = self.get_serializer_class()
        if 'context' in kwargs:
            kwargs['context'].update(self.get_serializer_context())
        else:
            kwargs['context'] = self.get_serializer_context()
        return serializer_class(*args, **kwargs)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.annotate(rank=models.Value('green', output_field=models.CharField()))

        extra_filter = dict()

        if 'project' in request.query_params:
            project_id = request.query_params.get('project')
            extra_filter.update({
                'project_id': project_id,
                'project__organization': get_current_organization(self.request)
            })
        else:
            raise ValidationError('Project is required.')

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise ValidationError('Project not found.')

        end_date = timezone.now()
        from_date = end_date - timezone.timedelta(days=14)
        commit_queryset = Commit.objects.filter(**extra_filter).order_by('timestamp')

        if request and 'timestamp__range' in request.query_params:
            value = request.query_params.get('timestamp__range')
            from_date, end_date = map(int, value.split(','))
            from_date, end_date = timezone.datetime.fromtimestamp(from_date, tz=pytz.UTC).replace(hour=0, minute=0,
                                                                                                  second=0,
                                                                                                  microsecond=0), timezone.datetime.fromtimestamp(
                end_date, tz=pytz.UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timezone.timedelta(days=2)
            lookup_expr = LOOKUP_SEP.join(['timestamp', 'range'])
            extra_filter.update({lookup_expr: (from_date, end_date)})
        else:
            if commit_queryset:
                end_date = commit_queryset.last().timestamp
                from_date = end_date - timezone.timedelta(days=14)
                lookup_expr = LOOKUP_SEP.join(['timestamp', 'range'])
                extra_filter.update({lookup_expr: (from_date, end_date)})

        risk_commit_queryset = commit_queryset.filter(timestamp__lte=from_date).order_by('timestamp')
        commit_queryset = commit_queryset.filter(**extra_filter).order_by('timestamp')

        if risk_commit_queryset or commit_queryset:
            b = Bugspots(project, risk_commit_queryset)
            # hotspots = b.get_hotspots()
            red_hotspots = b.get_red_hotspots()
            orange_hotspots = b.get_orange_hotspots()
            green_hotspots = b.get_green_hotspots()
            # serializer = self.get_serializer(queryset, many=True,
            #                                  context={'hotspots': hotspots, 'red_hotspots': red_hotspots,
            #                                           'orange_hotspots': orange_hotspots,
            #                                           'green_hotspots': green_hotspots})

            queryset = list(queryset)

            for item in queryset:

                for hotspot in red_hotspots:
                    if hotspot.filename[:len(item.full_filename)] == item.full_filename:
                        setattr(item, 'rank', 'red')
                        break

                for hotspot in orange_hotspots:
                    if hotspot.filename[:len(item.full_filename)] == item.full_filename:
                        setattr(item, 'rank', 'orange')
                        break

                for hotspot in green_hotspots:
                    if hotspot.filename[:len(item.full_filename)] == item.full_filename:
                        setattr(item, 'rank', 'green')
                        break

            serializer = self.get_serializer(queryset, many=True)
        else:
            serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['GET'], detail=False, url_path=r'(?P<parent_pk>[0-9]+)/childs')
    def childs(self, request, parent_pk=None):
        # queryset = self.filter_queryset(File.objects.filter(parent=parent_pk))
        queryset = self.filter_queryset(File.objects.filter(parent=parent_pk).annotate(
                descendant_count=models.ExpressionWrapper(
                    (
                            models.F('rght') - models.F('lft') - models.Value('1', output_field=models.IntegerField())
                    ) / models.Value('2', output_field=models.IntegerField()), output_field=models.IntegerField())
            ).annotate(
                has_childs=models.Case(
                    models.When(descendant_count__gt=0, then=True),
                    default=False, output_field=models.BooleanField()
                )
            ).prefetch_related('areas')
        )

        extra_filter = dict()

        if 'project' in request.query_params:
            project_id = request.query_params.get('project')
            extra_filter.update({
                'project_id': project_id,
                'project__organization': get_current_organization(self.request)
            })
        else:
            raise ValidationError('Project is required.')

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise ValidationError('Project not found.')

        end_date = timezone.now()
        from_date = end_date - timezone.timedelta(days=14)
        commit_queryset = Commit.objects.filter(**extra_filter).order_by('timestamp')

        if request and 'timestamp__range' in request.query_params:
            value = request.query_params.get('timestamp__range')
            from_date, end_date = map(int, value.split(','))
            from_date, end_date = timezone.datetime.fromtimestamp(from_date, tz=pytz.UTC).replace(hour=0, minute=0,
                                                                                                  second=0,
                                                                                                  microsecond=0), timezone.datetime.fromtimestamp(
                end_date, tz=pytz.UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timezone.timedelta(days=2)
            lookup_expr = LOOKUP_SEP.join(['timestamp', 'range'])
            extra_filter.update({lookup_expr: (from_date, end_date)})
        else:
            if commit_queryset:
                end_date = commit_queryset.last().timestamp
                from_date = end_date - timezone.timedelta(days=14)
                lookup_expr = LOOKUP_SEP.join(['timestamp', 'range'])
                extra_filter.update({lookup_expr: (from_date, end_date)})

        risk_commit_queryset = commit_queryset.filter(timestamp__lte=from_date).order_by('timestamp')
        commit_queryset = commit_queryset.filter(**extra_filter).order_by('timestamp')

        if risk_commit_queryset or commit_queryset:
            b = Bugspots(project, risk_commit_queryset)
            # hotspots = b.get_hotspots()
            red_hotspots = b.get_red_hotspots()
            orange_hotspots = b.get_orange_hotspots()
            green_hotspots = b.get_green_hotspots()
            # serializer = self.get_serializer(queryset, many=True,
            #                                  context={'hotspots': hotspots, 'red_hotspots': red_hotspots,
            #                                           'orange_hotspots': orange_hotspots,
            #                                           'green_hotspots': green_hotspots})

            queryset = list(queryset)

            for item in queryset:

                for hotspot in red_hotspots:
                    if hotspot.filename[:len(item.full_filename)] == item.full_filename:
                        setattr(item, 'rank', 'red')
                        break

                for hotspot in orange_hotspots:
                    if hotspot.filename[:len(item.full_filename)] == item.full_filename:
                        setattr(item, 'rank', 'orange')
                        break

                for hotspot in green_hotspots:
                    if hotspot.filename[:len(item.full_filename)] == item.full_filename:
                        setattr(item, 'rank', 'green')
                        break

            serializer = self.get_serializer(queryset, many=True)

        else:
            serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class TestTypeReportModelViewSet(MultiSerializerViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Test Type API endpoint
    ---
    list:
        List test types endpoint


    create:
        Create test type endpoint


    retrieve:
        Retrieve test type endpoint


    partial_update:
        Partial update test type endpoint


    update:
        Update test type endpoint


    """
    model = TestRunResult
    queryset = TestRunResult.objects.all()
    queryset_action = {
        'list': TestRunResult.objects.all(),
    }

    serializer_class = TestTypeReportSerializer
    serializer_action_classes = {
        'list': TestTypeReportSerializer,
    }

    filter_class = TestTypeReportFilterSet
    filter_action_classes = {
        'list': TestTypeReportFilterSet,
    }

    search_fields = ('^test_type_name',)
    search_action_fields = {
        'list': ('^test_type_name',)
    }

    ordering_fields = ()
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'test_type_pk'

    def get_queryset(self):
        queryset = super(TestTypeReportModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.values('test_type_id').annotate(
            tests__count=models.Count(
                models.Case(
                    models.When(test_type_id=models.F('test_type_id'), then=models.F('test_id')),

                ), distinct=True
            ),
            created_defects__count=models.Count(
                models.Case(
                    models.When(test_type_id=models.F('test_type_id'), then=models.F('created_defects__id'))
                ), distinct=True
            ),
            founded_defects__flaky_failure__count=models.Count(
                models.Case(
                    models.When(
                        models.Q(
                            test_type_id=models.F('test_type_id'),
                            founded_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]
                        ), then=models.F('founded_defects__id')
                    )
                ), distinct=True
            ),
            passed_tests__count=models.Count(
                models.Case(
                    models.When(
                        models.Q(
                            test_type_id=models.F('test_type_id'), status=TestRunResult.STATUS_PASS
                        ), then=models.F('test_id')
                    )
                ), distinct=True
            ),
            failed_tests__count=models.Count(
                models.Case(
                    models.When(
                        models.Q(
                            test_type_id=models.F('test_type_id'), status=TestRunResult.STATUS_FAIL
                        ), then=models.F('test_id')
                    )
                ), distinct=True
            ),
            broken_tests__count=models.Count(
                models.Case(
                    models.When(
                        models.Q(
                            test_type_id=models.F('test_type_id'), status=TestRunResult.STATUS_BROKEN
                        ), then=models.F('test_id')
                    )
                ), distinct=True
            ),
            not_run_tests__count=models.Count(
                models.Case(
                    models.When(
                        models.Q(
                            test_type_id=models.F('test_type_id'),
                            status__in=[TestRunResult.STATUS_PENDING, TestRunResult.STATUS_SKIPPED,
                                        TestRunResult.STATUS_NOT_RUN]
                        ), then=models.F('test_id')
                    )
                ), distinct=True
            ),
            id=models.F('test_type_id'),
            name=models.F('test_type_name'),

        ).values(
            'id',
            'name',

            'tests__count',
            'created_defects__count',
            'founded_defects__flaky_failure__count',

            'passed_tests__count',
            'failed_tests__count',
            'broken_tests__count',
            'not_run_tests__count',

            'project_id',
            'project_name',
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class TestSuiteReportModelViewSet(MultiSerializerViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Test Suite API endpoint
    ---
    list:
        List test suites endpoint


    create:
        Create test suite endpoint


    retrieve:
        Retrieve test suite endpoint


    partial_update:
        Partial update test suite endpoint


    update:
        Update test suite endpoint


    """
    model = TestRunResult
    queryset = TestRunResult.objects.all()
    queryset_action = {
        'list': TestRunResult.objects.all(),
    }

    serializer_class = TestSuiteReportSerializer
    serializer_action_classes = {
        'list': TestSuiteReportSerializer,
    }

    filter_class = TestSuiteReportFilterSet
    filter_action_classes = {
        'list': TestSuiteReportFilterSet,
    }

    ordering_fields = ()
    search_fields = ()
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'test_suite_pk'

    def get_queryset(self):
        queryset = super(TestSuiteReportModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        queryset_subquery = (
            queryset
                .filter(test_suite_id=models.OuterRef('test_suite_id'))
                .order_by('-test_run_id')
                .values('test_run_id')[:1]
        )

        qs = queryset.annotate(
            last_test_run_id=models.Subquery(queryset_subquery)
        ).values(
            'last_test_run_id'
        ).filter(
            test_run_id=models.F('last_test_run_id')
        ).order_by(
            'test_suite_id', 'test_id', '-id', '-created'
        ).values(
            'test_suite_id',
            'test_suite_name',
            'project_id',
            'project_name',
            'test_run_id',
            'test_id',
            'id',
            'status',
        )

        normalize_data = {}
        for item in qs:
            if item['test_suite_id'] not in normalize_data:
                normalize_data[item['test_suite_id']] = {
                    'tests': dict()
                }
            normalize_data[item['test_suite_id']]['test_run_id'] = item['test_run_id']

            normalize_data[item['test_suite_id']]['name'] = item['test_suite_name']
            normalize_data[item['test_suite_id']]['project_id'] = item['project_id']
            normalize_data[item['test_suite_id']]['project_name'] = item['project_name']
            if item['test_id'] not in normalize_data[item['test_suite_id']]['tests']:
                normalize_data[item['test_suite_id']]['tests'][item['test_id']] = list()
            normalize_data[item['test_suite_id']]['tests'][item['test_id']].append(item['status'])

        queryset = list()
        for key, value in normalize_data.items():
            test_suite = {}
            test_suite['id'] = key
            test_suite['name'] = value['name']
            test_suite['project_id'] = value['project_id']
            test_suite['project_name'] = value['project_name']
            test_suite['test_run_id'] = value['test_run_id']

            test_suite['tests__count'] = len(value['tests'])

            test_suite['passed_tests__count'] = 0
            test_suite['failed_tests__count'] = 0
            test_suite['broken_tests__count'] = 0
            test_suite['not_run_tests__count'] = 0

            for test_id, status_list in value['tests'].items():
                if len(status_list) == 0:
                    continue
                status = status_list[0]
                if status == TestRunResult.STATUS_PASS:
                    test_suite['passed_tests__count'] += 1
                elif status == TestRunResult.STATUS_FAIL:
                    test_suite['failed_tests__count'] += 1
                elif status == TestRunResult.STATUS_BROKEN:
                    test_suite['broken_tests__count'] += 1
                elif status in [TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN,
                                TestRunResult.STATUS_SKIPPED]:
                    test_suite['not_run_tests__count'] += 1
                else:
                    continue
            queryset.append(test_suite)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class TestRunReportModelViewSet(MultiSerializerViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Test Run API endpoint
    ---
    list:
        List test runs endpoint


    create:
        Create test run endpoint


    retrieve:
        Retrieve test run endpoint


    partial_update:
        Partial update test run endpoint


    update:
        Update test run endpoint


    """
    model = TestRunResult
    queryset = TestRunResult.objects.all()
    queryset_action = {
        'list': TestRunResult.objects.all().annotate(start_date=TruncSecond(models.F('test_run_start_date'))),
        'retrieve': TestRun.objects.all()
    }

    serializer_class = TestRunReportSerializer
    serializer_action_classes = {
        'list': TestRunReportSerializer,
        'retrieve': TestRunDetailReportSerializer
    }

    filter_class = TestRunReportFilterSet
    filter_action_classes = {
        'list': TestRunReportFilterSet,
        'retrieve': None
    }

    search_fields = ()
    ordering_fields = ('id', 'start_date', 'end_date',)
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'test_run_pk'

    def get_queryset(self):
        queryset = super(TestRunReportModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset

    def list(self, request, *args, **kwargs):
        # import time
        # start_time = time.time()
        queryset = self.filter_queryset(self.get_queryset())
        # print '#1: {}'.format(time.time()-start_time)
        sub_queryset = (
            queryset
                .filter(test_id=models.OuterRef('test_id'), test_run_id=models.OuterRef('test_run_id'))
                .values('status')[:1]
        )
        # print '#2: {}'.format(time.time() - start_time)
        qs = queryset.annotate(
            last_test_run_result=models.Subquery(sub_queryset)
        ).values(
            'test_run_id'
        ).annotate(
            tests__count=models.Count(
                models.Case(
                    models.When(test_run_id=models.F('test_run_id'), then=models.F('test_id')),
                ), distinct=True
            ),
            created_defects__count=models.Count(
                models.Case(
                    models.When(test_run_id=models.F('test_run_id'), then=models.F('created_defects__id'))
                ), distinct=True
            ),
            founded_defects__flaky_failure__count=models.Count(
                models.Case(
                    models.When(
                        models.Q(
                            test_run_id=models.F('test_run_id'),
                            founded_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_INVALID_TEST,
                                                       Defect.TYPE_ENVIRONMENTAL]
                        ), then=models.F('founded_defects__id')
                    )
                ), distinct=True
            ),
            passed_tests__count=models.Count(
                models.Case(
                    models.When(
                        models.Q(
                            # test_run_id=models.F('test_run_id'),
                            last_test_run_result=TestRunResult.STATUS_PASS
                        ), then=models.F('test_id')
                    )
                ), distinct=True
            ),
            failed_tests__count=models.Count(
                models.Case(
                    models.When(
                        models.Q(
                            # test_run_id=models.F('test_run_id'),
                            last_test_run_result=TestRunResult.STATUS_FAIL
                        ), then=models.F('test_id')
                    )
                ), distinct=True
            ),
            broken_tests__count=models.Count(
                models.Case(
                    models.When(
                        models.Q(
                            # test_run_id=models.F('test_run_id'),
                            last_test_run_result=TestRunResult.STATUS_BROKEN
                        ), then=models.F('test_id')
                    )
                ), distinct=True
            ),
            not_run_tests__count=models.Count(
                models.Case(
                    models.When(
                        models.Q(
                            # test_run_id=models.F('test_run_id'),
                            last_test_run_result__in=[TestRunResult.STATUS_PENDING, TestRunResult.STATUS_SKIPPED,
                                                      TestRunResult.STATUS_NOT_RUN]
                        ), then=models.F('test_id')
                    )
                ), distinct=True
            ),
            id=models.F('test_run_id'),
            name=models.F('test_run_name'),
            type=models.F('test_run_type'),
            start_date=TruncSecond(models.F('test_run_start_date')),
            end_date=models.Case(
                models.When(
                    ~models.Q(test_run_end_date=None),
                    then=TruncSecond(models.F('test_run_end_date'))
                )
            ),
        ).values(
            'project_id',
            'project_name',

            'test_suite_id',
            'test_suite_name',

            'id',
            'name',

            'start_date',
            'end_date',

            'tests__count',
            'created_defects__count',
            'founded_defects__flaky_failure__count',
            'passed_tests__count',
            'failed_tests__count',
            'broken_tests__count',
            'not_run_tests__count',

        )
        # print '#3: {}'.format(time.time() - start_time)
        queryset = qs
        # print '#4: {}'.format(time.time() - start_time)
        page = self.paginate_queryset(queryset)
        # print '#5: {}'.format(time.time() - start_time)
        if page is not None:
            # print '#6.0: {}'.format(time.time() - start_time)
            serializer = self.get_serializer(page, many=True)
            # print '#6.1: {}'.format(time.time() - start_time)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        # print '#6.2: {}'.format(time.time() - start_time)
        # data =
        # print '#7: {}'.format(time.time() - start_time)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class TestReportModelViewSet(MultiSerializerViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Test API endpoint
    ---
    list:
        List tests endpoint


    changed:
        Changed list tests endpoint


    slowest:
        Show very slow tests endpoint


    graph_execution_time:
        Date grouped graph execution time tests endpoint


    """
    test_runs_ml_using_threshold = 500
    minimal_number_of_testruns_for_ml_model_usnig = 50


    model = Test
    queryset = Test.objects.all()

    serializer_class = TestReportSerializer
    serializer_action_classes = {
        # 'list': TestReportSerializer,
        'flakiness': TestFlakinessReportSerializer,
        'changed': TestChangedReportSerializer,
        'slowest': TestSlowestReportSerializer,
        'graph_execution_time': TestExecutionTimeGraphSerializer,
        'graph_execution_time_avg': TestExecutionTimeAvgGraphSerializer,
        'graph_status_passed': TestStatusPassedGraphSerializer,

        # # PRIO TESTS
        # 'high': TestPrioritizeReportSerializer,
        # 'unassigned': TestPrioritizeReportSerializer,
        # 'open_defect': TestPrioritizeReportSerializer,
        # 'ready_defect': TestPrioritizeReportSerializer,
        #
        # 'medium': TestPrioritizeReportSerializer,
        # 'low': TestPrioritizeReportSerializer,
        # 'rerun': TestPrioritizeReportSerializer,

    }

    # filter_class = TestReportFilterSet
    # filter_action_classes = {}

    search_fields = ()
    ordering_fields = ()
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'test_pk'

    def get_queryset(self):
        queryset = super(TestReportModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        extra_filters = dict()
        if 'current_status' in request.query_params:
            value = request.query_params['current_status']
            value_list = [x.lstrip().rstrip() for x in value.split(u',')]
            if TestRunResult.STATUS_SKIPPED in value_list:
                value_list.extend([TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN])
            lookup_expr = LOOKUP_SEP.join(['current_status', 'in'])
            extra_filters.update({lookup_expr: value_list})

        if 'defect' in request.query_params:
            value = request.query_params['defect']
            lookup_expr = LOOKUP_SEP.join(['associated_defects', 'exact'])
            extra_filters.update({lookup_expr: value})

        newest_test_run = TestRun.objects.filter(
            id__in=set(list(queryset.values_list('test_runs__id', flat=True)))).order_by('-end_date').first()

        if 'test_run' in request.query_params:
            value = request.query_params['test_run']
            try:
                newest_test_run = TestRun.objects.get(id=value)
            except TestRun.DoesNotExist:
                raise APIException('TestRun not found!')

        newest_current_test_run_results = TestRunResult.objects.filter(
            test_run=newest_test_run, test=models.OuterRef('id')).order_by('-execution_ended')

        queryset = queryset.annotate(
            current_status=models.Subquery(newest_current_test_run_results.values('status')[:1])
        ).filter(
            **extra_filters
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['GET', ], detail=False, url_path=r'graph/execution')
    def graph_execution_time(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        queryset = queryset.filter(test_runs__end_date__isnull=False).annotate(
            timestamp=functions.TruncDay(models.F('test_runs__start_date'))).order_by('timestamp')

        queryset = queryset.values('timestamp').annotate(
            __passed_count=models.Count(
                models.Case(
                    models.When(
                        test_runs__test_run_results__status=TestRunResult.STATUS_PASS, then=models.F('id')
                    )
                ), distinct=True
            ),
            __failed_count=models.Count(
                models.Case(
                    models.When(
                        test_runs__test_run_results__status=TestRunResult.STATUS_FAIL, then=models.F('id')
                    )
                ), distinct=True
            ),
            __broken_count=models.Count(
                models.Case(
                    models.When(
                        test_runs__test_run_results__status=TestRunResult.STATUS_BROKEN, then=models.F('id')
                    )
                ), distinct=True
            ),
        ).values(
            'timestamp',
            '__passed_count',
            '__failed_count',
            '__broken_count'
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['GET', ], detail=False, url_path=r'graph/execution/avg')
    def graph_execution_time_avg(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        queryset = queryset.filter(test_runs__test_run_results__execution_ended__isnull=False).annotate(
            timestamp=functions.TruncDay(
                models.F('test_runs__test_run_results__execution_ended'))
        ).order_by('timestamp')

        queryset = queryset.values('timestamp').annotate(
            __execution_time=models.Avg(
                models.Case(
                    models.When(
                        id=models.F('id'), then=models.F('test_runs__test_run_results__execution_time')
                    )
                ), distinct=True
            ),

        ).values(
            'timestamp',
            '__execution_time'
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['GET', ], detail=False, url_path=r'graph/status/passed')
    def graph_status_passed(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        queryset = queryset.filter(
            test_runs__test_run_results__execution_ended__isnull=False
        ).annotate(
            timestamp=functions.TruncDay(models.F('test_runs__test_run_results__execution_ended'))
        ).order_by('timestamp')

        queryset = queryset.values('timestamp').annotate(
            __count=models.Count(
                models.Case(
                    models.When(
                        ~models.Q(test_runs__test_run_results__status__in=[
                            TestRunResult.STATUS_NOT_RUN,
                            TestRunResult.STATUS_SKIPPED,
                            TestRunResult.STATUS_PENDING
                        ]),
                        then=models.F('id')
                    )
                ), distinct=True
            ),
            __count_passed_status=models.Count(
                models.Case(
                    models.When(
                        test_runs__test_run_results__status=TestRunResult.STATUS_PASS, then=models.F('id')
                    )
                ), distinct=True
            ),
        ).annotate(
            percentage_of_passed_results=models.F('__count_passed_status') * 100 / models.F('__count')
        ).values(
            'timestamp',
            'percentage_of_passed_results',
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_group_flaky_tests_queryset(self, queryset):
        extra_filters = dict()

        newest_test_run = TestRun.objects.filter(
            id__in=set(list(queryset.values_list('test_runs__id', flat=True)))).order_by('-created').first()

        if self.request.query_params.has_key('test_run'):
            value = self.request.query_params['test_run']
            try:
                newest_test_run = TestRun.objects.get(id=value)
            except TestRun.DoesNotExist:
                raise APIException('TestRun not found!')

        if self.request.query_params.has_key('current_status'):
            value = self.request.query_params['current_status']
            value = [x.lstrip().rstrip() for x in value.split(u',')]
            if TestRunResult.STATUS_SKIPPED in value:
                value.extend([TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN])
            lookup_expr = LOOKUP_SEP.join(['current_status', 'in'])
            extra_filters = {lookup_expr: value}

        queryset_subquery = (
            TestRunResult
            .objects
            .filter(
                test_id=models.OuterRef('id'),
                test_run=newest_test_run
            )
            .order_by('-created')
            .values('status')[:1]
        )

        queryset = queryset.annotate(current_status=models.Subquery(queryset_subquery))

        flaky_test_passed_test_run_result_queryset = queryset.filter(
            models.Q(current_status=TestRunResult.STATUS_PASS) &
            models.Q(associated_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]) &
            models.Q(associated_defects__created_by_test_run=newest_test_run)
        )

        flaky_test_failed_test_run_result_queryset = queryset.filter(
            models.Q(
                models.Q(current_status=TestRunResult.STATUS_FAIL) &
                models.Q(associated_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]) &
                models.Q(associated_defects__created_by_test_run=newest_test_run)
            )
            | models.Q(
                models.Q(current_status=TestRunResult.STATUS_FAIL) &
                models.Q(associated_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]) &
                models.Q(associated_defects__created_by_test_run=newest_test_run.previous_test_run)
            )
        )

        flaky_test_broken_test_run_result_queryset = queryset.filter(
            models.Q(current_status=TestRunResult.STATUS_BROKEN) &
            models.Q(associated_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]) &
            models.Q(associated_defects__created_by_test_run=newest_test_run)
        )

        flaky_test_not_run_test_run_result_queryset = queryset.filter(
            models.Q(current_status__in=[TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN,
                                                          TestRunResult.STATUS_SKIPPED]) &
            models.Q(associated_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL]) &
            models.Q(associated_defects__created_by_test_run=newest_test_run)
        )

        queryset = (
            flaky_test_passed_test_run_result_queryset
            | flaky_test_failed_test_run_result_queryset
            | flaky_test_broken_test_run_result_queryset
            | flaky_test_not_run_test_run_result_queryset
        )

        queryset = queryset.filter(
            **extra_filters
        )
        return queryset

    @action(methods=['GET', ], detail=False, url_path=r'group/flaky')
    def group_flaky_tests(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = self.get_group_flaky_tests_queryset(queryset).distinct()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_group_invalid_tests_queryset(self, queryset):
        extra_filters = dict()
        if self.request.query_params.has_key('current_status'):
            value = self.request.query_params['current_status']
            value = [x.lstrip().rstrip() for x in value.split(u',')]
            if TestRunResult.STATUS_SKIPPED in value:
                value.extend([TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN])
            lookup_expr = LOOKUP_SEP.join(['current_status', 'in'])
            extra_filters = {lookup_expr: value}

        queryset_subquery = (
            TestRunResult
            .objects
            .filter(
                test_id=models.OuterRef('id'),
                test_run__id__in=set(list(queryset.values_list('test_runs__id', flat=True)))
            )
            .order_by('-created')
            .values('status')[:1]
        )
        queryset = queryset.annotate(current_status=models.Subquery(queryset_subquery))
        queryset = queryset.filter(**extra_filters)
        queryset = queryset.filter(
            models.Q(associated_defects__type=Defect.TYPE_INVALID_TEST) &
            ~models.Q(associated_defects__status=Defect.STATUS_CLOSED)
        )
        return queryset

    @action(methods=['GET', ], detail=False, url_path=r'group/invalid')
    def group_invalid_tests(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = self.get_group_invalid_tests_queryset(queryset).distinct()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_group_open_defect_tests_queryset(self, queryset):
        extra_filters = dict()
        if self.request.query_params.has_key('current_status'):
            value = self.request.query_params['current_status']
            value = [x.lstrip().rstrip() for x in value.split(u',')]
            if TestRunResult.STATUS_SKIPPED in value:
                value.extend([TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN])
            lookup_expr = LOOKUP_SEP.join(['current_status', 'in'])
            extra_filters = {lookup_expr: value}

        queryset_subquery = (
            TestRunResult
            .objects
            .filter(
                test_id=models.OuterRef('id'),
                test_run__id__in=set(list(queryset.values_list('test_runs__id', flat=True)))
            )
            .order_by('-created')
            .values('status')[:1]
        )
        queryset = queryset.annotate(current_status=models.Subquery(queryset_subquery))
        queryset = queryset.filter(**extra_filters)
        queryset = queryset.filter(
            models.Q(associated_defects__type__in=[Defect.TYPE_PROJECT, Defect.TYPE_LOCAL]) &
            ~models.Q(associated_defects__status__in=[Defect.STATUS_NEW, Defect.STATUS_CLOSED, Defect.STATUS_READY])
        )
        return queryset

    @action(methods=['GET', ], detail=False, url_path=r'group/open-defect')
    def group_open_defect_tests(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = self.get_group_open_defect_tests_queryset(queryset).distinct()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_group_ready_tests_queryset(self, queryset):
        extra_filters = dict()
        if self.request.query_params.has_key('current_status'):
            value = self.request.query_params['current_status']
            value = [x.lstrip().rstrip() for x in value.split(u',')]
            if TestRunResult.STATUS_SKIPPED in value:
                value.extend([TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN])
            lookup_expr = LOOKUP_SEP.join(['current_status', 'in'])
            extra_filters = {lookup_expr: value}

        queryset_subquery = (
            TestRunResult
                .objects
                .filter(
                test_id=models.OuterRef('id'),
                test_run__id__in=set(list(queryset.values_list('test_runs__id', flat=True)))
            )
                .order_by('-created')
                .values('status')[:1]
        )
        queryset = queryset.annotate(current_status=models.Subquery(queryset_subquery))
        queryset = queryset.filter(**extra_filters)
        queryset = queryset.filter(
            models.Q(associated_defects__type=Defect.TYPE_PROJECT) &
            models.Q(associated_defects__status=Defect.STATUS_READY)
        )
        return queryset

    @action(methods=['GET', ], detail=False, url_path=r'group/ready-defect')
    def group_ready_defect_tests(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = self.get_group_ready_tests_queryset(queryset).distinct()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_group_passed_tests_queryset(self, queryset):
        extra_filters = dict()
        if self.request.query_params.has_key('current_status'):
            value = self.request.query_params['current_status']
            value = [x.lstrip().rstrip() for x in value.split(u',')]
            if TestRunResult.STATUS_SKIPPED in value:
                value.extend([TestRunResult.STATUS_PENDING, TestRunResult.STATUS_NOT_RUN])
            lookup_expr = LOOKUP_SEP.join(['current_status', 'in'])
            extra_filters = {lookup_expr: value}

        newest_test_run = TestRun.objects.filter(
            id__in=set(list(queryset.values_list('test_runs__id', flat=True)))).order_by('-created').first()

        if self.request.query_params.has_key('test_run'):
            value = self.request.query_params['test_run']
            try:
                newest_test_run = TestRun.objects.get(id=value)
            except TestRun.DoesNotExist:
                raise APIException('TestRun not found!')

        newest_current_test_run_results = TestRunResult.objects.filter(test_run=newest_test_run, test=models.OuterRef('id')).order_by('-created')

        queryset = queryset.annotate(
            current_status=models.Subquery(newest_current_test_run_results.values('status')[:1])
        )
        queryset = queryset.filter(**extra_filters)
        queryset = queryset.exclude(
            models.Q(id__in=set(list(self.get_group_flaky_tests_queryset(queryset).values_list('id', flat=True)))) |
            models.Q(id__in=set(list(self.get_group_invalid_tests_queryset(queryset).values_list('id', flat=True)))) |
            models.Q(id__in=set(list(self.get_group_open_defect_tests_queryset(queryset).values_list('id', flat=True)))) |
            models.Q(id__in=set(list(self.get_group_ready_tests_queryset(queryset).values_list('id', flat=True))))
        )
        return queryset

    @action(methods=['GET', ], detail=False, url_path=r'group/passed')
    def group_passed_tests(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = self.get_group_passed_tests_queryset(queryset).distinct()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['GET', ], detail=False, url_path=r'flakiness')
    def flakiness(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        queryset_subquery = (
            TestRunResult
                .objects
                .filter(test_id=models.OuterRef('id'))
                .order_by('-created')
                .values('status')
        )

        queryset = queryset.annotate(
            __count=models.Count('id'),
            last_test_run_results=ArraySubquery(queryset_subquery[:10]),
            flaky_failure__count=models.Count(
                models.Case(
                    models.When(
                        associated_defects__type__in=[
                            Defect.TYPE_FLAKY,
                            Defect.TYPE_ENVIRONMENTAL
                        ],
                        then=models.F('associated_defects')
                    ), output_field=models.IntegerField()
                ), distinct=True
            )
        ).annotate(
            percentage_of_flaky_failure_results=models.F('flaky_failure__count') * 100 / models.F('__count')
        ).filter(
            percentage_of_flaky_failure_results__gt=0
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['GET', ], detail=False, url_path=r'changed')
    def changed(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        newest_test_run = TestRun.objects.filter(
            id__in=set(list(queryset.values_list('test_runs__id', flat=True)))).order_by('-created').first()

        if 'test_run' in request.query_params:
            value = request.query_params['test_run']
            try:
                newest_test_run = TestRun.objects.get(id=value)
            except TestRun.DoesNotExist:
                raise APIException('TestRun not found!')

        newest_current_test_run_results = TestRunResult.objects.filter(test_run=newest_test_run,
                                                                       test=models.OuterRef('id')).order_by('-created')

        newest_previous_test_run_results = TestRunResult.objects.filter(test_run=newest_test_run.previous_test_run,
                                                                        test=models.OuterRef('id')).order_by('-created')

        queryset = queryset.annotate(
            current_status=models.Subquery(newest_current_test_run_results.values('status')[:1]),
            previous_status=models.Subquery(newest_previous_test_run_results.values('status')[:1])
        ).filter(
            ~models.Q(current_status=models.F('previous_status'))
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['GET', ], detail=False, url_path=r'slowest')
    def slowest(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        aggregate_execution_time_avg = queryset.values('test_runs__test_run_results__execution_time').aggregate(
            execution_time_avg=models.Avg('test_runs__test_run_results__execution_time')
        )

        queryset = queryset.filter(
            execution_time__gt=aggregate_execution_time_avg['execution_time_avg']
        ).values('id').annotate(
            execution_time_min=models.Min('test_runs__test_run_results__execution_time',
                                          output_field=models.FloatField()),
            execution_time_avg=models.Avg('test_runs__test_run_results__execution_time',
                                          output_field=models.FloatField()),
            execution_time_max=models.Max('test_runs__test_run_results__execution_time',
                                          output_field=models.FloatField()),
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_open_defect_queryset(self, queryset):
        extra_filters = dict()
        if self.request.query_params.has_key('commit'):
            value = self.request.query_params['commit']
            lookup_expr = LOOKUP_SEP.join(['test_suites__test_runs__commit__id', 'exact'])
            extra_filters = {lookup_expr: value}

        queryset = queryset.filter(**extra_filters)
        queryset = self.filter_queryset(queryset)

        queryset = queryset.filter(
            associated_defects__type__not_in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL],
            associated_defects__status__in=[Defect.STATUS_IN_PROGRESS, Defect.STATUS_VERIFIED],
        )
        return queryset

    @action(methods=['GET', ], detail=False, url_path=r'open-defect')
    def open_defect(self, request, *args, **kwargs):
        # queryset = self.filter_queryset(self.get_queryset())
        queryset = self.get_queryset()
        queryset = self.get_open_defect_queryset(queryset).distinct('name')
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_ready_defect_queryset(self, queryset):
        extra_filters = dict()
        if self.request.query_params.has_key('commit'):
            value = self.request.query_params['commit']
            lookup_expr = LOOKUP_SEP.join(['test_suites__test_runs__commit__id', 'exact'])
            extra_filters = {lookup_expr: value}

        queryset = queryset.filter(**extra_filters)
        queryset = self.filter_queryset(queryset)
        exclude_test_ids = set(list(self.get_open_defect_queryset(queryset).values_list('id', flat=True)))
        queryset = queryset.exclude(id__in=exclude_test_ids)

        queryset = queryset.filter(
            associated_defects__type__not_in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL],
            associated_defects__status=Defect.STATUS_READY,
        )
        return queryset.distinct('name')

    @action(methods=['GET', ], detail=False, url_path=r'ready-defect')
    def ready_defect(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        queryset = self.get_ready_defect_queryset(queryset)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @staticmethod
    def get_last_run_result_commit(project, target_branch, test_suite):
        """
        Return last commit of commits set that has 'target_branch' in 'branches' and have test runs.

        If no one commit will be found we raise exception

        :param project: py:obj:`Project` object
        :param target_branch: py:obj:`Branch` object
        :param test_suite: py:obj:`TestSuite` object
        :return: py:obj:`Commit` object or may raise NotFound exception
        """
        last_run_commit_list = Commit.objects.filter(project=project,
                                                     branches=target_branch,
                                                     test_runs__isnull=False,
                                                     test_runs__test_suite=test_suite).order_by('-timestamp')
        if len(last_run_commit_list) == 0:
            first_commit = Commit.objects.filter(project=project,
                                                     branches=target_branch).order_by('timestamp')[:1]
            if len(first_commit) == 0:
                err_msg = "No one commit in branch '{0}' has not associated "                                 \
                        "test runs in specified test suite '{1}'".format(target_branch.name, test_suite.name)
                raise NotFound(detail=err_msg)
            return first_commit[0]
        return last_run_commit_list[0]

    @staticmethod
    def get_commits_list(target_branch, first_commit, second_commit, exclusive=False):
        """
        This function finds all commits contained in target branch and placed in inheritance chain between the first and
        the second commit.

        If flag 'exclusive' is set, then last commit in inheritance chain will be excluded.

        :param target_branch: py:obj:`Branch` object
        :param first_commit: py:obj:`Commit` object
        :param second_commit: py:obj:`Commit` object
        :param exclusive: boolean
        :return: instance of py:obj:`Commit`
        """
        if first_commit.timestamp < second_commit.timestamp:
            ancestor = first_commit
            descendant = second_commit
        else:
            ancestor = second_commit
            descendant = first_commit

        if exclusive:
            query = Q(timestamp__gte=ancestor.timestamp, timestamp__lt=descendant.timestamp)
        else:
            query = Q(timestamp__gte=ancestor.timestamp, timestamp__lte=descendant.timestamp)
        return target_branch.commits.filter(query).values_list('id', flat=True)

    def _get_commit_list_from_request(self):
        """
        This function return list of commit ids based on request params

        Request query param should contains next:
            commit_type - one of ['Single', 'LastRun', 'BetweenInclusive', 'BetweenExclusive']
            commit - first commit id
            from_commit - second commit id. Needed only for ['BetweenInclusive', 'BetweenExclusive']
            target_branch - Needed for ['LastRun','BetweenInclusive', 'BetweenExclusive'].
                            This argument specified target branch.

        Allowed commit types:
            Single - we return list that contains only 'commit'
            LastRun - we search last commit in specified branch that has associated test runs. After that
                      we return list of commit between specified commit and founded commit.
            BetweenInclusive - return every commit between two specified commits.
            BetweenExclusive - return every commit between two specified commits excluding earlier commit.

        :return: list of commits ids or may raise one of this exceptions: APIException, ValidationError.
        """
        project_id = self.request.query_params.get('project')
        if not project_id:
            raise ValidationError({'detail': "Argument 'project' not specified"})
        elif isinstance(project_id, str) and not re.match(r'^\d*$', project_id):
            raise ValidationError({'detail': "Argument 'project' should be integer"})
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise ValidationError({'detail': "Project with id {0} isn't exists".format(project_id)})

        commit = None
        from_commit = None
        for arg in ('commit', 'from_commit'):
            commit_arg = self.request.query_params.get(arg)

            if commit_arg:
                if isinstance(commit_arg, str) and not re.match(r'^\d*$', commit_arg):
                    raise ValidationError({'detail': "Argument '{0}' should be integer".format(arg)})
                try:
                    commit_arg = Commit.objects.get(project=project, id=commit_arg)
                    if arg == 'commit':
                        commit = commit_arg
                    elif arg == 'from_commit':
                        from_commit = commit_arg
                    else:
                        raise APIException('Unknown argument type')
                except Commit.DoesNotExist:
                    raise ValidationError({'detail': "Commit from '{0}' not found".format(commit_arg)})

        target_branch_id = self.request.query_params.get('target_branch')
        if target_branch_id:
            if isinstance(target_branch_id, str) and not re.match(r'^\d*$', target_branch_id):
                raise ValidationError({'detail': "Argument 'target_branch' should be integer"})
            try:
                target_branch = Branch.objects.get(project=project, id=target_branch_id)
            except Branch.DoesNotExist:
                raise ValidationError({'detail': "Invalid value of 'target_branch'"})
        else:
            target_branch = None

        test_suite_id = self.request.query_params.get('test_suite')
        if test_suite_id:
            if isinstance(test_suite_id, str) and not re.match(r'^\d*$', test_suite_id):
                raise ValidationError({'detail': "Argument 'test_suite' should be integer"})
            try:
                test_suite = TestSuite.objects.get(project=project, id=test_suite_id)
            except TestSuite.DoesNotExist:
                raise ValidationError({'detail': "Invalid value of 'test_suite'"})
        else:
            test_suite = None

        commit_type = self.request.query_params.get('commit_type')
        if not commit_type or commit_type == 'Single':
            if not commit:
                raise ValidationError({'detail': "Argument 'commit' is not specified"})
            if from_commit:
                raise ValidationError({'detail': "Argument 'from_commit' not needed."})
            commits_ids = [commit.id]
        elif commit_type == 'LastRun':
            if not target_branch:
                raise ValidationError({'detail': "Argument 'target_branch' is not specified"})
            if not commit:
                raise ValidationError({'detail': "Argument 'commit' is not specified"})
            if not test_suite:
                raise ValidationError({'detail': "Argument 'test_suite' is not specified"})
            if from_commit:
                raise ValidationError({'detail': "Argument 'from_commit' not needed."})
            last_res_commit = self.get_last_run_result_commit(project, target_branch, test_suite)
            commits_ids = self.get_commits_list(target_branch, commit, last_res_commit)
        elif commit_type in ['BetweenInclusive', 'BetweenExclusive']:
            if not target_branch:
                raise ValidationError({'detail': "Argument 'target_branch' is not specified"})
            if not commit:
                raise ValidationError({'detail': "Argument 'commit' is not specified"})
            if not from_commit:
                raise ValidationError({'detail': "Argument 'from_commit' is not specified"})
            if commit_type == 'BetweenInclusive':
                commits_ids = self.get_commits_list(target_branch, commit, from_commit)
            else:
                commits_ids = self.get_commits_list(target_branch, commit, from_commit, exclusive=True)
        else:
            raise ValidationError({'detail': "'{0}' is wrong value of 'CommitType' argument".format(commit_type)})
        return commits_ids

    @staticmethod
    def get_default_high_queryset(queryset, commits_ids):
        """

        High tests:
        * Tests that have associations with files that have filechanges related with
          specified commits

        * If test associated with defects that have type=TYPE_PROJECT, status=STATUS_CLOSED and
          close_type in [Defect.CLOSE_TYPE_FIXED, Defect.CLOSE_TYPE_WONT_FIX].
          Also this defects should have associations with filechanges (through 'caused_by_commit' field) for file that
          has associated filechange in specified commit.

        :param queryset:
        :param commits_ids:
        :return:
        """
        commits_files_changes_query = Commit.objects.filter(id__in=commits_ids).values_list('files', flat=True)
        file_query_set = queryset.filter(associated_files__in=Subquery(commits_files_changes_query))

        queryset = queryset.filter(project__commits__id__in=commits_ids)
        queryset = queryset.annotate(
            filechange__file_id=models.F('project__commits__filechange__file_id'),
        ).filter(
            associated_defects__type=Defect.TYPE_PROJECT,
            associated_defects__status=Defect.STATUS_CLOSED,
            associated_defects__close_type__in=[Defect.CLOSE_TYPE_FIXED, Defect.CLOSE_TYPE_WONT_FIX],
            filechange__file_id=models.F('associated_defects__caused_by_commits__filechange__file_id')
        )
        high_priority_query = Q(id__in=file_query_set.values_list('id', flat=True))
        high_priority_query |= Q(id__in=queryset.values_list('id', flat=True))
        return Test.objects.filter(high_priority_query).distinct('name')

    def get_high_queryset(self, queryset):
        """
        This function returns high priority tests queryset.


        :param queryset:
        :return queryset:
        """
        queryset = self.filter_queryset(queryset)
        commits_ids = self._get_commit_list_from_request()

        test_suite_id = self.request.query_params.get('test_suite', None)
        if test_suite_id is not None:
            try:
                test_suite = TestSuite.objects.get(id=test_suite_id)
                num_testruns = test_suite.test_runs.count()
                project_id = test_suite.project_id
            except TestSuite.DoesNotExist:
                raise ValidationError("Test suite with id '{0}' doesn't exists.".format(test_suite_id))
            ml_predictor = MLPredictor(test_suite_id=test_suite_id)
            ml_model_existing_flag = ml_predictor.is_loaded
            if ml_model_existing_flag is False or num_testruns < self.minimal_number_of_testruns_for_ml_model_usnig:
                return self.get_default_high_queryset(queryset, commits_ids)
            else:
                commits_queryset = Commit.objects.filter(id__in=commits_ids)
                if num_testruns >= self.test_runs_ml_using_threshold:
                    high_tests = ml_predictor.get_test_prioritization(queryset, commits_queryset)['h']
                    return high_tests.distinct('name')
                else:
                    ml_prediction_results = ml_predictor.get_test_prioritization(queryset, commits_queryset)
                    ml_unassigned_tests_num = ml_prediction_results['u'].count()
                    original_unassigned_num = self.get_unassigned_queryset(queryset).count()
                    if original_unassigned_num > ml_unassigned_tests_num:
                        return ml_prediction_results['h'].distinct('name')
                    else:
                        return self.get_default_high_queryset(queryset, commits_ids)
        else:
            return self.get_default_high_queryset(queryset, commits_ids)

    @action(methods=['GET', ], detail=False, url_path=r'high')
    def high(self, request, *args, **kwargs):
        """
        This function handles request for high tests.

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        queryset = self.get_queryset()
        queryset = self.get_high_queryset(queryset)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_default_medium_queryset(self, queryset, commits_ids):
        """
        Medium tests:
        * Tests that aren't included in high test set.
        AND (
            * Tests that have associations with areas(include 5 level recursion through areas that
            depends from test associated areas) that associated with specified commits.
                OR
            * Tests that associated with defects that have type=TYPE_PROJECT, status=STATUS_CLOSED and
            close_type in [Defect.CLOSE_TYPE_FIXED, Defect.CLOSE_TYPE_WONT_FIX].
            Also this defects have areas that associated with commit's areas.
        )
        :param queryset:
        :param commits_ids:
        :return:
        """
        area_query_set = queryset.filter(models.Q(associated_areas__isnull=False))
        commits_areas = list(Commit.objects.filter(id__in=commits_ids).values_list('areas', flat=True))
        depended_areas_annotations = {'depended_area_lvl%d' % i:
                                      models.F('associated_areas'+(LOOKUP_SEP+'dependencies')*i) for i in range(1, 6)}
        area_query_set = area_query_set.annotate(**depended_areas_annotations)
        area_query_filter = Q(associated_areas__in=commits_areas)
        for depended_area_level in depended_areas_annotations.keys():
            area_query_filter |= Q(**{LOOKUP_SEP.join([depended_area_level, 'in']): commits_areas})
        area_query_set = area_query_set.filter(area_query_filter)

        queryset = queryset.filter(project__commits__id__in=commits_ids)
        queryset = queryset.filter(
            associated_defects__type=Defect.TYPE_PROJECT,
            associated_defects__status=Defect.STATUS_CLOSED,
            associated_defects__close_type__in=[Defect.CLOSE_TYPE_FIXED, Defect.CLOSE_TYPE_WONT_FIX],
        )

        default_area_id = Area.get_default(project=self.request.query_params['project']).id
        queryset = queryset.annotate(
            commit__areas=models.F('project__commits__areas'),
            caused_by_commits__areas=models.F('associated_defects__caused_by_commits__areas')
        ).filter(
            ~Q(commit__areas=default_area_id) &
            Q(
                models.Q(commit__areas=models.F('caused_by_commits__areas')) |
                models.Q(commit__areas=models.F('area'))
            )
        )
        medium_query = Q(id__in=area_query_set.values_list('id', flat=True))
        medium_query |= Q(id__in=queryset.values_list('id', flat=True))

        filtered_queryset = self.filter_queryset(self.get_queryset())
        high_queryset = self.get_default_high_queryset(filtered_queryset, commits_ids)
        exclude_test_ids = set(list(high_queryset.values_list('id', flat=True)))
        return Test.objects.exclude(id__in=exclude_test_ids).filter(medium_query).distinct('name')

    def get_medium_queryset(self, queryset):
        """
        This function returns medium priority tests queryset.

        :param queryset:
        :return queryset:
        """
        commits_ids = self._get_commit_list_from_request()
        queryset = self.filter_queryset(queryset)

        test_suite_id = self.request.query_params.get('test_suite', None)
        if test_suite_id is not None:
            try:
                test_suite = TestSuite.objects.get(id=test_suite_id)
                num_testruns = test_suite.test_runs.count()
                project_id = test_suite.project_id
            except TestSuite.DoesNotExist:
                raise ValidationError("Test suite with id '{0}' doesn't exists.".format(test_suite_id))
            ml_predictor = MLPredictor(test_suite_id=test_suite_id)
            ml_model_existing_flag = ml_predictor.is_loaded
            if ml_model_existing_flag is False or num_testruns < self.minimal_number_of_testruns_for_ml_model_usnig:
                return self.get_default_medium_queryset(queryset, commits_ids)
            else:
                commits_queryset = Commit.objects.filter(id__in=commits_ids)
                if num_testruns >= self.test_runs_ml_using_threshold:
                    medium_tests = ml_predictor.get_test_prioritization(queryset, commits_queryset)['m']
                    return medium_tests.distinct('name')
                else:
                    ml_prediction_results = ml_predictor.get_test_prioritization(queryset, commits_queryset)
                    ml_unassigned_tests_num = ml_prediction_results['u'].count()
                    original_unassigned_num = self.get_unassigned_queryset(queryset).count()
                    if original_unassigned_num > ml_unassigned_tests_num:
                        return ml_prediction_results['m'].distinct('name')
                    else:
                        return self.get_default_medium_queryset(queryset, commits_ids)
        else:
            return self.get_default_medium_queryset(queryset, commits_ids)

    @action(methods=['GET', ], detail=False, url_path=r'medium')
    def medium(self, request, *args, **kwargs):
        """
        This function handles request for medium tests.

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        queryset = self.get_queryset()
        queryset = self.get_medium_queryset(queryset)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_unassigned_queryset(self, queryset):
        """
        This function returns unassigned priority tests queryset.

        Unassigned tests:
        * Tests that aren't not included in high and medium sets.
        AND
        * Tests haven't associated defects with type=TYPE_PROJECT.
        AND
        * Tests haven't associated files and areas.

        :param queryset:
        :return queryset:
        """
        queryset = self.filter_queryset(queryset)
        exclude_test_ids = Test.objects.filter(
            associated_defects__type=Defect.TYPE_PROJECT
        ).values_list('id', flat=True)
        queryset = queryset.exclude(id__in=exclude_test_ids)
        queryset = queryset.exclude(Q(associated_files__isnull=False) | Q(associated_areas__isnull=False))
        return queryset.distinct('name')

    @action(methods=['GET', ], detail=False, url_path=r'unassigned')
    def unassigned(self, request, *args, **kwargs):
        """
        This function handles request for unassigned tests.

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        queryset = self.get_queryset()
        queryset = self.get_unassigned_queryset(queryset)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_default_low_queryset(self, queryset, commits_ids):
        exclude_test_ids = set(list(self.get_default_high_queryset(queryset, commits_ids).values_list('id', flat=True)))
        queryset = queryset.exclude(id__in=exclude_test_ids)

        exclude_test_ids = set(list(self.get_default_medium_queryset(queryset, commits_ids).values_list('id', flat=True)))
        queryset = queryset.exclude(id__in=exclude_test_ids)

        exclude_test_ids = set(list(self.get_unassigned_queryset(queryset).values_list('id', flat=True)))
        queryset = queryset.exclude(id__in=exclude_test_ids)
        return queryset.distinct('name')

    def get_low_queryset(self, queryset):
        """
        This function returns low priority tests queryset.

        Low tests:
        * All tests that aren't included in high, medium and unassigned sets.

        :param queryset:
        :return queryset:
        """
        commits_ids = self._get_commit_list_from_request()
        queryset = self.filter_queryset(queryset)
        test_suite_id = self.request.query_params.get('test_suite', None)
        if test_suite_id is not None:
            try:
                test_suite = TestSuite.objects.get(id=test_suite_id)
                num_testruns = test_suite.test_runs.count()
                project_id = test_suite.project_id
            except TestSuite.DoesNotExist:
                raise ValidationError("Test suite with id '{0}' doesn't exists.".format(test_suite_id))
            ml_predictor = MLPredictor(test_suite_id=test_suite_id)
            ml_model_existing_flag = ml_predictor.is_loaded
            if ml_model_existing_flag is False or num_testruns < self.minimal_number_of_testruns_for_ml_model_usnig:
                return self.get_default_low_queryset(queryset, commits_ids)
            else:
                commits_queryset = Commit.objects.filter(id__in=commits_ids)
                if num_testruns >= self.test_runs_ml_using_threshold:
                    low_tests = ml_predictor.get_test_prioritization(queryset, commits_queryset)['l']
                    return low_tests.distinct('name')
                else:
                    ml_prediction_results = ml_predictor.get_test_prioritization(queryset, commits_queryset)
                    ml_unassigned_tests_num = ml_prediction_results['u'].count()
                    original_unassigned_num = self.get_unassigned_queryset(queryset).count()
                    if original_unassigned_num > ml_unassigned_tests_num:
                        return ml_prediction_results['l'].distinct('name')
                    else:
                        return self.get_default_low_queryset(queryset, commits_ids)
        else:
            return self.get_default_low_queryset(queryset, commits_ids)

    def get_default_top20_queryset(self, queryset, commits_ids, percent):
        default_queryset = list()

        commit_id = self.request.query_params.get('commit', None)
        if commit_id is None:
            commit_id = self.request.query_params.get('from_commit', None)
        result = calculate_similar_by_commit(queryset, commit_id, percent=percent)
        test_ids = result['tests']

        default_queryset.extend(list(self.get_default_high_queryset(queryset, commits_ids).values_list('id', flat=True)))
        default_queryset.extend(list(self.get_default_medium_queryset(queryset, commits_ids).values_list('id', flat=True)))
        default_queryset.extend(list(self.get_unassigned_queryset(queryset).values_list('id', flat=True)))
        if len(test_ids) > 0:
            default_queryset.extend(list(test_ids))

        _ids = default_queryset

        _count = queryset.count()
        _per = percent * _count / 100
        _ids = default_queryset[:_per]

        return Test.objects.filter(id__in=_ids).distinct('name')

    def get_top20_queryset(self, queryset):
        commits_ids = self._get_commit_list_from_request()
        queryset = self.filter_queryset(queryset)

        test_suite_id = self.request.query_params.get('test_suite', None)
        percent = 20

        if test_suite_id is not None:
            try:
                test_suite = TestSuite.objects.get(id=test_suite_id)
                num_testruns = test_suite.test_runs.count()
                project_id = test_suite.project_id
            except TestSuite.DoesNotExist:
                raise ValidationError("Test suite with id '{0}' doesn't exists.".format(test_suite_id))

            ml_predictor = MLPredictor(test_suite_id=test_suite_id)
            ml_model_existing_flag = ml_predictor.is_loaded

            if ml_model_existing_flag is False:
                return self.get_default_by_percent_queryset(queryset, commits_ids, percent)
            else:
                commits_queryset = Commit.objects.filter(id__in=commits_ids)
                tests = ml_predictor.get_test_prioritization_top_by_percent(queryset, commits_queryset, percent)
                return tests
        else:
            return self.get_default_top20_queryset(queryset, commits_ids, percent)

    # def get_test_name_for_testsuite(self, queryset):
    #     priority_param   = self.request.query_params.get('priority')
    #     project_id_param = self.request.query_params.get('project')
    #     day              = self.request.query_params.get('day')
    #     try:
    #         list_name_test_suite = TestSuite.objects.filter(project_id = project_id_param, priority = priority_param)
    #         name_for_search = list()
    #         name_test = Test.objects.values_list('name', 'created').filter(priority = priority_param, project_id = project_id_param)
    #         if list_name_test_suite:
    #             for name_test_suite in list_name_test_suite:
    #                 name_for_search.append(name_test_suite.name)
    #             name_test = name_test.filter(testsuite_name__in = name_for_search)

    #         if day is not None and int(priority_param) == 11:
    #             to_date   = datetime.datetime.now()
    #             from_date = to_date - timedelta(days=int(day))
    #             name_test  = name_test.filter(created__range=(from_date, to_date))
    #     except:
    #         raise APIException('Test not found!')

    #     return name_test

    def get_all_queryset(self, queryset):
        """
        This function returns all tests queryset.

        :param queryset:
        :return queryset:
        """
        priority = self.request.query_params.get('priority')
        day      = self.request.query_params.get('day')
        queryset = self.filter_queryset(queryset)
        if day is not None and int(priority) == 11:
            try:
                day_val = int(day)
                if day_val < 0:
                    raise APIException('Please enter a valid number of days.')
            except ValueError:
                raise APIException('Please enter a valid number of days.')
            to_date   = datetime.datetime.now()
            from_date = to_date - timedelta(days=day_val)
            queryset = queryset.filter(created__range=(from_date, to_date))
        return queryset.distinct('name')

    def get_default_by_percent_queryset(self, queryset, commits_ids, percent):
        default_queryset = list()
        commit_id = self.request.query_params.get('commit', None)
        if commit_id is None:
            commit_id = self.request.query_params.get('from_commit', None)
        result = calculate_similar_by_commit(queryset, commit_id, percent=percent)
        test_ids = result['tests']

        default_queryset.extend(list(self.get_default_high_queryset(queryset, commits_ids).values_list('id', flat=True)))
        default_queryset.extend(list(self.get_default_medium_queryset(queryset, commits_ids).values_list('id', flat=True)))
        default_queryset.extend(list(self.get_default_low_queryset(queryset, commits_ids).values_list('id', flat=True)))
        default_queryset.extend(list(self.get_unassigned_queryset(queryset).values_list('id', flat=True)))
        if len(test_ids) > 0:
            default_queryset.extend(list(test_ids))

        _count = queryset.count()
        _per = int(percent * _count / 100)
        _ids = default_queryset[:_per]

        return Test.objects.filter(id__in=_ids).distinct('name')

    def get_top_by_percent_queryset(self, queryset):
        commits_ids = self._get_commit_list_from_request()
        queryset = self.filter_queryset(queryset)

        test_suite_id = self.request.query_params.get('test_suite', None)

        if 'percent' in self.request.query_params:
            percent = int(self.request.query_params.get('percent', 20))
        elif 'percentage' in self.request.query_params:
            percent = int(self.request.query_params.get('percentage', 20))
        else:
            percent = 20

        if test_suite_id is not None:
            try:
                test_suite = TestSuite.objects.get(id=test_suite_id)
                num_testruns = test_suite.test_runs.count()
                project_id = test_suite.project_id
            except TestSuite.DoesNotExist:
                raise ValidationError("Test suite with id '{0}' doesn't exists.".format(test_suite_id))

            ml_predictor = MLPredictor(test_suite_id=test_suite_id)
            ml_model_existing_flag = ml_predictor.is_loaded

            if ml_model_existing_flag is False:
                return self.get_default_by_percent_queryset(queryset, commits_ids, percent)
            else:
                commits_queryset = Commit.objects.filter(id__in=commits_ids)
                tests = ml_predictor.get_test_prioritization_top_by_percent(queryset, commits_queryset, percent)
                return tests
        else:
            return self.get_default_by_percent_queryset(queryset, commits_ids, percent)

    @action(methods=['GET', ], detail=False, url_path=r'low')
    def low(self, request, *args, **kwargs):
        """
        This function handles request for low tests.

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        queryset = self.get_queryset()
        queryset = self.get_low_queryset(queryset)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_rerun_queryset(self, queryset):
        extra_filters = dict()
        if 'commit' in self.request.query_params:
            commit_id = self.request.query_params['commit']
            lookup_expr = LOOKUP_SEP.join(['test_runs__commit__id', 'exact'])
            extra_filters = {lookup_expr: commit_id}

        queryset = queryset.filter(**extra_filters)
        queryset = self.filter_queryset(queryset)

        newest_test_run = TestRun.objects.filter(
            id__in=set(list(queryset.values_list('test_runs__id', flat=True)))).order_by('-created').first()

        if 'test_run' in self.request.query_params:
            value = self.request.query_params['test_run']
            try:
                newest_test_run = TestRun.objects.get(id=value)
            except TestRun.DoesNotExist:
                raise APIException('TestRun not found!')

        newest_current_test_run_results = TestRunResult.objects.filter(test_run=newest_test_run,
                                                                       test=models.OuterRef('id'))
        if 'commit' in self.request.query_params:
            commit_id = self.request.query_params['commit']
            newest_current_test_run_results = newest_current_test_run_results.filter(commit_id=commit_id)

        newest_current_test_run_results = newest_current_test_run_results.annotate(
            __count=functions.Coalesce(models.Count('*'), 0)
        ).order_by('-created')

        queryset = queryset.annotate(
            runtest_result_count=models.Subquery(newest_current_test_run_results.values('__count')[:1]),
            current_status=models.Subquery(newest_current_test_run_results.values('status')[:1])
        ).filter(
            runtest_result_count=1,
            current_status__in=[TestRunResult.STATUS_FAIL, TestRunResult.STATUS_BROKEN, TestRunResult.STATUS_ERROR]
        )
        return queryset.distinct('name')

    @action(methods=['GET', ], detail=False, url_path=r'rerun')
    def rerun(self, request, *args, **kwargs):
        # queryset = self.filter_queryset(self.get_queryset())
        queryset = self.get_queryset()
        queryset = self.get_rerun_queryset(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class TestRunResultReportModelViewSet(MultiSerializerViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Test Run Result API endpoint
    ---
    list:
        List test run results endpoint


    create:
        Create test run result endpoint


    retrieve:
        Retrieve test run result endpoint


    partial_update:
        Partial update test run result endpoint


    update:
        Update test run result endpoint


    """
    model = TestRunResult
    serializer_class = TestRunResultReportSerializer
    queryset = TestRunResult.objects.order_by('-created')
    filter_class = TestRunResultReportFilterSet

    search_fields = ()
    ordering_fields = ()
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'test_run_result_pk'

    def get_queryset(self):
        queryset = super(TestRunResultReportModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset


class DefectReportModelViewSet(MultiSerializerViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Defect API endpoint
    ---
    list:
        List defects endpoint


    create:
        Create defect endpoint


    retrieve:
        Retrieve defect endpoint


    partial_update:
        Partial update defect endpoint


    update:
        Update defect endpoint


    """
    model = Defect
    serializer_class = DefectReportSerializer
    queryset = Defect.objects.all()

    filter_class = DefectReportFilterSet

    search_fields = ('name',)
    ordering_fields = ('id', 'name', 'status', 'priority', 'severity', 'found_date', 'owner', 'type')
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'defect_pk'

    def get_queryset(self):
        queryset = super(DefectReportModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset

    def list(self, request, *args, **kwargs):
        # TODO: add request validation
        queryset = self.filter_queryset(self.get_queryset())

        test_ids = set(list(queryset.values_list('associated_tests__id', flat=True)))
        test_run_ids = set(list(queryset.values_list('found_test_runs__id', flat=True)))

        queryset_subquery = (
            TestRunResult.objects
                .filter(test_id=models.OuterRef('id'), test_run_id__in=test_run_ids)
                .order_by('-created')
                .values('status')[:1]
        )

        prefetch_passed_associated_tests = models.Prefetch(
            'associated_tests',
            queryset=Test.objects.filter(
                id__in=test_ids,
                test_runs__id__in=test_run_ids
            ).annotate(
                current_status=models.Subquery(queryset_subquery)
            ).filter(
                current_status=TestRunResult.STATUS_PASS
            ),
            to_attr='passed_associated_tests',
        )

        prefetch_failed_associated_tests = models.Prefetch(
            'associated_tests',
            queryset=Test.objects.filter(
                id__in=test_ids,
                test_runs__id__in=test_run_ids
            ).annotate(
                current_status=models.Subquery(queryset_subquery)
            ).filter(
                current_status=TestRunResult.STATUS_FAIL
            ),
            to_attr='failed_associated_tests',
        )

        prefetch_broken_associated_tests = models.Prefetch(
            'associated_tests',
            queryset=Test.objects.filter(
                id__in=test_ids,
                test_runs__id__in=test_run_ids
            ).annotate(
                current_status=models.Subquery(queryset_subquery)
            ).filter(
                current_status=TestRunResult.STATUS_BROKEN
            ),
            to_attr='broken_associated_tests',
        )

        prefetch_not_run_associated_tests = models.Prefetch(
            'associated_tests',
            queryset=Test.objects.filter(
                id__in=test_ids,
                test_runs__id__in=test_run_ids
            ).annotate(
                current_status=models.Subquery(queryset_subquery)
            ).filter(
                current_status__in=[
                    TestRunResult.STATUS_PENDING,
                    TestRunResult.STATUS_SKIPPED,
                    TestRunResult.STATUS_NOT_RUN
                ]
            ),
            to_attr='not_run_associated_tests',
        )

        queryset = queryset.prefetch_related(
            prefetch_passed_associated_tests,
            prefetch_failed_associated_tests,
            prefetch_broken_associated_tests,
            prefetch_not_run_associated_tests
        )

        queryset = queryset.annotate(
            associated_tests__count=models.Count('associated_tests__id', distinct=True),
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # @swagger_auto_schema(responses={200: DefectSeverityReportSerializer()})
    @action(methods=['GET', ], detail=False)
    def severity(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        trivial_severity_queryset = queryset.filter(severity=Defect.SEVERITY_TRIVIAL)
        minor_severity_queryset = queryset.filter(severity=Defect.SEVERITY_MINOR)
        major_severity_queryset = queryset.filter(severity=Defect.SEVERITY_MAJOR)
        critical_severity_queryset = queryset.filter(severity=Defect.SEVERITY_CRITICAL)
        severity = dict(
            trivial=dict(
                new=trivial_severity_queryset.filter(status=Defect.STATUS_NEW).count(),
                in_progress=trivial_severity_queryset.filter(status=Defect.STATUS_IN_PROGRESS).count(),
                ready=trivial_severity_queryset.filter(status=Defect.STATUS_READY).count(),
                closed=trivial_severity_queryset.filter(status=Defect.STATUS_CLOSED).count()
            ),
            minor=dict(
                new=minor_severity_queryset.filter(status=Defect.STATUS_NEW).count(),
                in_progress=minor_severity_queryset.filter(status=Defect.STATUS_IN_PROGRESS).count(),
                ready=minor_severity_queryset.filter(status=Defect.STATUS_READY).count(),
                closed=minor_severity_queryset.filter(status=Defect.STATUS_CLOSED).count()
            ),
            major=dict(
                new=major_severity_queryset.filter(status=Defect.STATUS_NEW).count(),
                in_progress=major_severity_queryset.filter(status=Defect.STATUS_IN_PROGRESS).count(),
                ready=major_severity_queryset.filter(status=Defect.STATUS_READY).count(),
                closed=major_severity_queryset.filter(status=Defect.STATUS_CLOSED).count()
            ),
            critical=dict(
                new=critical_severity_queryset.filter(status=Defect.STATUS_NEW).count(),
                in_progress=critical_severity_queryset.filter(status=Defect.STATUS_IN_PROGRESS).count(),
                ready=critical_severity_queryset.filter(status=Defect.STATUS_READY).count(),
                closed=critical_severity_queryset.filter(status=Defect.STATUS_CLOSED).count()
            )
        )
        serializer = DefectSeverityReportSerializer(severity, many=False)
        return Response(serializer.data)

    # @swagger_auto_schema(responses={200: DefectSummaryReportSerializer()})
    @action(methods=['GET', ], detail=False)
    def summary(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        trivial_severity_queryset = queryset.filter(severity=Defect.SEVERITY_TRIVIAL)
        minor_severity_queryset = queryset.filter(severity=Defect.SEVERITY_MINOR)
        major_severity_queryset = queryset.filter(severity=Defect.SEVERITY_MAJOR)
        critical_severity_queryset = queryset.filter(severity=Defect.SEVERITY_CRITICAL)
        severity = dict(
            trivial=dict(
                new=trivial_severity_queryset.filter(status=Defect.STATUS_NEW).count(),
                in_progress=trivial_severity_queryset.filter(status=Defect.STATUS_IN_PROGRESS).count(),
                ready=trivial_severity_queryset.filter(status=Defect.STATUS_READY).count(),
                closed=trivial_severity_queryset.filter(status=Defect.STATUS_CLOSED).count()
            ),
            minor=dict(
                new=minor_severity_queryset.filter(status=Defect.STATUS_NEW).count(),
                in_progress=minor_severity_queryset.filter(status=Defect.STATUS_IN_PROGRESS).count(),
                ready=minor_severity_queryset.filter(status=Defect.STATUS_READY).count(),
                closed=minor_severity_queryset.filter(status=Defect.STATUS_CLOSED).count()
            ),
            major=dict(
                new=major_severity_queryset.filter(status=Defect.STATUS_NEW).count(),
                in_progress=major_severity_queryset.filter(status=Defect.STATUS_IN_PROGRESS).count(),
                ready=major_severity_queryset.filter(status=Defect.STATUS_READY).count(),
                closed=major_severity_queryset.filter(status=Defect.STATUS_CLOSED).count()
            ),
            critical=dict(
                new=critical_severity_queryset.filter(status=Defect.STATUS_NEW).count(),
                in_progress=critical_severity_queryset.filter(status=Defect.STATUS_IN_PROGRESS).count(),
                ready=critical_severity_queryset.filter(status=Defect.STATUS_READY).count(),
                closed=critical_severity_queryset.filter(status=Defect.STATUS_CLOSED).count()
            )
        )

        data = dict(
            severity=severity,
            create_type=queryset.aggregate(
                automatic=models.Count(models.Case(models.When(create_type=Defect.CREATE_TYPE_AUTOMATIC, then=1))),
                manual=models.Count(models.Case(models.When(create_type=Defect.CREATE_TYPE_MANUAL, then=1))),
            ),
            number_of_defects=queryset.count(),
            number_of_open_defects=queryset.exclude(status=Defect.STATUS_CLOSED).count(),

        )
        serializer = DefectSummaryReportSerializer(data, many=False)
        return Response(serializer.data)

    # @swagger_auto_schema(responses={200: DefectOpenStatusGraphSerializer()})
    @action(methods=['GET', ], detail=False, url_path=r'graph/open')
    def graph_open_defect(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # for item in queryset.values('id', 'found_date', 'close_date'):
        #     print item

        queryset = queryset.annotate(
            timestamp=functions.TruncDay(models.F('found_date')),
            close_timestamp=models.Case(
                models.When(
                    close_date__isnull=False, then=functions.TruncDay(models.F('close_date'))
                ), default=None
            )
        ).order_by('timestamp', 'close_timestamp')

        # for item in queryset.values('id', 'timestamp', 'close_timestamp'):
        #     print item

        data = collections.defaultdict(int)
        graph_data = {}

        for item in queryset.values('id', 'status', 'timestamp', 'close_timestamp'):

            timestamp = item['timestamp']
            if timestamp is not None:
                timestamp = item['timestamp'].replace(tzinfo=None)

            close_timestamp = item['close_timestamp']
            if close_timestamp is not None:
                close_timestamp = close_timestamp.replace(tzinfo=None)

            # if item['id'] == 233:
            #     print timestamp, close_timestamp

            # if timestamp == close_timestamp:
            #     continue

            if not timestamp in data:
                data[timestamp] = 0

            if close_timestamp is not None and not close_timestamp in data:
                data[close_timestamp] = 0

        sorted_data = sorted(data.items(), key=operator.itemgetter(0))

        for item in queryset.values('id', 'status', 'timestamp', 'close_timestamp'):
            timestamp = item['timestamp']
            if timestamp is not None:
                timestamp = item['timestamp'].replace(tzinfo=None)

            close_timestamp = item['close_timestamp']
            if close_timestamp is not None:
                close_timestamp = close_timestamp.replace(tzinfo=None)
            else:
                close_timestamp = (timestamp + timezone.timedelta(days=365))

            for date, _ in sorted_data:

                if not date in graph_data:
                    graph_data[date] = 0

                if timestamp <= date and date < close_timestamp:
                    graph_data[date] += 1

        queryset = [{'timestamp': key, '__count': value} for key, value in graph_data.items()]
        serializer = DefectOpenStatusGraphSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # @swagger_auto_schema(responses={200: DefectNewStatusGraphSerializer()})
    @action(methods=['GET', ], detail=False, url_path=r'graph/new')
    def graph_new_defect(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        queryset = queryset.annotate(timestamp=functions.TruncDay(models.F('found_date'))).order_by('timestamp')
        queryset = queryset.values('timestamp').annotate(__count=models.Count('id', distinct=True)).values('timestamp',
                                                                                                           '__count')

        serializer = DefectNewStatusGraphSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # @swagger_auto_schema(responses={200: DefectCloseDurationTimeGraphSerializer(many=True)})
    @action(methods=['GET', ], detail=False, url_path=r'graph/duration/close')
    def graph_close_duration_defect(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.filter(
            status=Defect.STATUS_CLOSED
        ).order_by('found_date').annotate(
            timestamp=functions.TruncDay(models.F('found_date')),
        ).values('timestamp').annotate(
            __duration=models.F('close_date') - models.F('found_date')
        ).values('__duration', 'timestamp')

        serializer = DefectCloseDurationTimeGraphSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # @swagger_auto_schema(responses={200: SeverityGraphSerializer()})
    @action(methods=['GET', ], detail=False, url_path=r'graph/severity/open')
    def graph_open_defect_by_severity(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.exclude(
            status=Defect.STATUS_CLOSED
        ).order_by('found_date').values('found_date').annotate(
            timestamp=functions.TruncDay(models.F('found_date')),
        ).values('timestamp').annotate(
            __count_trivial=models.Count(
                models.Case(
                    models.When(
                        severity=Defect.SEVERITY_TRIVIAL,
                        then=models.F('id')
                    )
                ), distinct=True
            ),
            __count_minor=models.Count(
                models.Case(
                    models.When(
                        severity=Defect.SEVERITY_MINOR,
                        then=models.F('id')
                    )
                ), distinct=True
            ),
            __count_major=models.Count(
                models.Case(
                    models.When(
                        severity=Defect.SEVERITY_MAJOR,
                        then=models.F('id')
                    )
                ), distinct=True
            ),
            __count_critical=models.Count(
                models.Case(
                    models.When(
                        severity=Defect.SEVERITY_CRITICAL,
                        then=models.F('id')
                    )
                ), distinct=True
            ),
        ).values('timestamp', '__count_trivial', '__count_minor', '__count_major', '__count_critical')

        serializer = SeverityGraphSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # @swagger_auto_schema(responses={200: SeverityGraphSerializer()})
    @action(methods=['GET', ], detail=False, url_path=r'graph/severity/all')  # TODO: NEED REMOVE /all prefix
    def graph_all_defect_by_severity(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.exclude(
            status=Defect.STATUS_CLOSED
        ).order_by('found_date').values('found_date').annotate(
            timestamp=functions.TruncDay(models.F('found_date')),
        ).values('timestamp').annotate(
            __count_trivial=models.Count(
                models.Case(
                    models.When(
                        severity=Defect.SEVERITY_TRIVIAL,
                        then=models.F('id')
                    )
                ), distinct=True
            ),
            __count_minor=models.Count(
                models.Case(
                    models.When(
                        severity=Defect.SEVERITY_MINOR,
                        then=models.F('id')
                    )
                ), distinct=True
            ),
            __count_major=models.Count(
                models.Case(
                    models.When(
                        severity=Defect.SEVERITY_MAJOR,
                        then=models.F('id')
                    )
                ), distinct=True
            ),
            __count_critical=models.Count(
                models.Case(
                    models.When(
                        severity=Defect.SEVERITY_CRITICAL,
                        then=models.F('id')
                    )
                ), distinct=True
            ),
        ).values('timestamp', '__count_trivial', '__count_minor', '__count_major', '__count_critical')

        serializer = SeverityGraphSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # @swagger_auto_schema(responses={200: DefectByTypeChartSerializer()})
    @action(methods=['GET', ], detail=False, url_path=r'chart/type')
    def chart_by_type(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.values('type').annotate(
            __count=models.Count('id', distinct=True),
        ).values('type', '__count')
        serializer = DefectByTypeChartSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AnalysisViewSet(MultiSerializerViewSetMixin, viewsets.GenericViewSet):
    queryset = Commit.objects.all()

    serializer_class = AnalysisFullUsernameSerializer
    serializer_action_classes = {
        'user': AnalysisUserSerializer,
        'get_username': AnalysisFullUsernameSerializer,
        'graph_range': AnalysisRangeGraphSerializer,
        'team': AnalysisTeamSerializer,
        'analysis': AnalysisTeamsSerializer,
    }

    def get_queryset(self):
        queryset = super(AnalysisViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset

    # username_param = openapi.Parameter(str('username'), openapi.IN_QUERY, description=str(''),
    #                                    type=openapi.TYPE_STRING)
    #
    # range_param = openapi.Parameter(str('data_range'), openapi.IN_QUERY, description=str(''), type=openapi.TYPE_ARRAY)

    # @swagger_auto_schema(method='GET', manual_parameters=[username_param])
    @action(['GET', ], detail=False, url_path=r'user/range')
    def graph_range(self, request, *args, **kwargs):
        graph_serializer = self.get_serializer_class()
        if request.query_params.get('username'):
            queryset = self.get_queryset().filter(author__name=request.query_params.get('username'))
        else:
            return Response(data={}, status=status.HTTP_200_OK)
        timestamp_expr = {}

        if request and 'project' in request.query_params:
            project_id = request.query_params.get('project')
            queryset = queryset.filter(project_id=project_id)

        if request and 'area' in request.query_params:
            area_id = request.query_params.get('area')
            queryset = queryset.filter(areas__in=[area_id])

        if request and 'timestamp__range' in request.query_params:
            value = request.query_params.get('timestamp__range')
            from_date, end_date = map(int, value.split(','))
            from_date, end_date = timezone.datetime.fromtimestamp(from_date, tz=pytz.UTC).replace(hour=0, minute=0,
                                                                                                  second=0,
                                                                                                  microsecond=0), \
                                  timezone.datetime.fromtimestamp(end_date, tz=pytz.UTC).replace(hour=23, minute=59,
                                                                                                 second=59,
                                                                                                 microsecond=0)
            lookup_expr = LOOKUP_SEP.join(['timestamp', 'range'])
            timestamp_expr = {lookup_expr: (from_date, end_date)}
        else:
            if queryset:
                end_date = queryset.last().timestamp
                from_date = end_date - timezone.timedelta(days=30)
                lookup_expr = LOOKUP_SEP.join(['timestamp', 'range'])
                timestamp_expr = {lookup_expr: (from_date, end_date)}

        queryset = queryset.filter(**timestamp_expr)
        queryset = queryset.annotate(parents_count=Count('parents')).exclude(parents_count__gte=2)

        result = calculate_user_analysis_by_range(queryset=queryset, timestamp__range=timestamp_expr)

        graph_serializer = graph_serializer(data=result)
        graph_serializer.is_valid(raise_exception=True)

        return Response(data=graph_serializer.data, status=status.HTTP_200_OK)

    # @swagger_auto_schema(method='GET', manual_parameters=[username_param])
    @action(['GET', ], detail=False, url_path=r'user')
    def user(self, request, *args, **kwargs):

        queryset = self.get_queryset().filter(author__name=request.query_params.get('username'))
        queryset = queryset.annotate(parents_count=Count('parents')).exclude(parents_count__gte=2)
        result = calculate_user_analysis(queryset=queryset)
        serializer = AnalysisUserSerializer(result, many=False)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(['GET', ], detail=False, url_path=r'users')
    def get_username(self, request, *args, **kwargs):
        serializer = self.get_serializer_class()
        user = request.user
        organization = get_current_organization(request=self.request)
        if organization:
            if organization.is_admin(user):
                username_unique_list = [user.get('author_name') for user in self.get_queryset().annotate(
                    author_name=KeyTextTransform('name', 'author')
                ).values('author_name').distinct() if user.get('author_name')]

                serializer = serializer(data={'username': username_unique_list})
                serializer.is_valid(raise_exception=True)

                return Response(data=serializer.data, status=status.HTTP_200_OK)
            else:
                user_commit = Commit.objects.filter(sender=user)
                if user_commit.exists():
                    author = user_commit.first().author.get('name')
                    serializer = serializer(data={'username': [author]})
                    serializer.is_valid(raise_exception=True)

                    return Response(data=serializer.data, status=status.HTTP_200_OK)
                else:
                    authors_list = list(self.get_queryset().values('author'))
                    username_unique_list = set([author.get('author', {}).get('name') for author in authors_list])
                    if user.username in username_unique_list:
                        serializer = serializer(data={'username': [user.username]})
                        serializer.is_valid(raise_exception=True)

                        return Response(data=serializer.data, status=status.HTTP_200_OK)
                    else:
                        return Response(data=[], status=status.HTTP_200_OK)

        return Response(data=[], status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(['GET', ], detail=False, url_path=r'team/old')
    def team(self, request, *args, **kwargs):
        user = request.user
        organization = get_current_organization(request=request)
        if organization:
            if organization.is_admin(user):
                queryset = self.get_queryset()
                authors_list = list(queryset.values('author'))
                authors_unique_list = {author.get('author').get('name', None): author.get('author') for author in
                                       authors_list if author.get('author').get('name', None)}.values()
                if request and 'project' in request.query_params:
                    project_id = request.query_params.get('project')
                    queryset = queryset.filter(project_id=project_id)

                if request and 'area' in request.query_params:
                    area_id = request.query_params.get('area')
                    queryset = queryset.filter(areas=area_id)

                timestamp_expr = {}
                if request and 'timestamp__range' in request.query_params:
                    value = request.query_params.get('timestamp__range')
                    from_date, end_date = map(int, value.split(','))
                    from_date, end_date = timezone.datetime.fromtimestamp(from_date, tz=pytz.UTC).replace(hour=0,
                                                                                                          minute=0,
                                                                                                          second=0,
                                                                                                          microsecond=0), \
                                          timezone.datetime.fromtimestamp(end_date, tz=pytz.UTC).replace(hour=23,
                                                                                                         minute=59,
                                                                                                         second=59,
                                                                                                         microsecond=0)
                    lookup_expr = LOOKUP_SEP.join(['timestamp', 'range'])
                    timestamp_expr = {lookup_expr: (from_date, end_date)}
                else:
                    if queryset:
                        end_date = queryset.last().timestamp
                        from_date = end_date - timezone.timedelta(days=30)
                        lookup_expr = LOOKUP_SEP.join(['timestamp', 'range'])
                        timestamp_expr = {lookup_expr: (from_date, end_date)}

                queryset = queryset.filter(**timestamp_expr)
                queryset = queryset.annotate(parents_count=Count('parents')).exclude(parents_count__gte=2)

                avg = {}
                result = list()
                max_output = 0
                max_commits = 0

                for author in authors_unique_list:

                    user = {
                        'username': author.get('name'),
                        'email': author.get('email'),
                        'output': 0,
                        'commits': 0,
                        'defects': 0,
                        'rework': 0
                    }
                    if not author.get('name', None):
                        continue

                    user_queryset = queryset.filter(author__name=author.get('name'))

                    queryset_defects = user_queryset.exclude(caused_defects__isnull=True)

                    user['output'] = avg_per_range(user_queryset.values('output', 'timestamp'), 'output',
                                                   timestamp_expr.get('timestamp__range'))
                    user['commits'] = avg_per_range(user_queryset.values('id', 'timestamp'), 'commits',
                                                    timestamp_expr.get('timestamp__range'))
                    user['rework'] = avg_per_range(user_queryset.values('rework', 'timestamp'), 'rework',
                                                   timestamp_expr.get('timestamp__range'))
                    user['defects'] = float(
                        queryset_defects.count()) / user_queryset.count() * 100 if user_queryset.count() > 0 else 0
                    user['timestamp_last_commit'] = Commit.objects.filter(author__name=author.get('name')).order_by(
                        'timestamp').last().timestamp
                    max_output = user['output'] if user['output'] > max_output else max_output
                    max_commits = user['commits'] if user['commits'] > max_commits else max_commits
                    result.append(user)

                avg['output'] = [user.get('output') for user in result if user.get('output') > 0]
                avg['commits'] = [user.get('commits') for user in result if user.get('commits') > 0]
                avg['defects'] = [user.get('defects') for user in result if user.get('defects') > 0]
                avg['rework'] = [user.get('rework') for user in result if user.get('rework') > 0]

                avg['output'] = sum(avg['output']) / len(avg['output']) if len(avg['output']) > 0 else 0
                avg['commits'] = sum(avg['commits']) / len(avg['commits']) if len(avg['commits']) > 0 else 0
                avg['defects'] = sum(avg['defects']) / len(avg['defects']) if len(avg['defects']) > 0 else 0
                avg['rework'] = sum(avg['rework']) / len(avg['rework']) if len(avg['rework']) > 0 else 0

                if request and 'ordering' in request.query_params:
                    ordering_fields = request.query_params.get('ordering').split(',')
                    if len(ordering_fields) == 1:
                        if request.query_params.get('ordering')[0] == '-':
                            result = sorted(result, key=operator.itemgetter(request.query_params.get('ordering')[1:]),
                                            reverse=True)
                        else:
                            result = sorted(result, key=operator.itemgetter(request.query_params.get('ordering')))

                page = self.paginate_queryset(result)
                data_serializer = {'users': page, 'avg': avg, 'max_output': max_output, 'max_commits': max_commits}
                if page is not None:
                    serializer = self.get_serializer(data_serializer)
                    return self.get_paginated_response(serializer.data)

                serializer = self.get_serializer(data_serializer)
                return Response(serializer.data)

        return Response({}, status=status.HTTP_403_FORBIDDEN)

    @action(methods=['GET', ], detail=False, url_path=r'team/new')
    def analysis(self, request, project_pk=None, *args, **kwargs):
        queryset = self.get_queryset().annotate(author_name=KeyTextTransform('name', 'author')).order_by('author_name')
        queryset = queryset.annotate(author_email=KeyTextTransform('email', 'author')).order_by('author_name')
        filtered_queryset = queryset

        if request and 'project' in request.query_params:
            project_id = request.query_params.get('project')
            filtered_queryset = queryset.filter(project_id=project_id)

        if request and 'area' in request.query_params:
            area_id = request.query_params.get('area')
            filtered_queryset = queryset.filter(areas__in=[area_id])

        # if request and 'timestamp__range' in request.query_params:
        #     value = request.query_params.get('timestamp__range')
        #     from_date, end_date = map(int, value.split(','))
        #     from_date, end_date = timezone.datetime.fromtimestamp(from_date, tz=pytz.UTC).replace(hour=0, minute=0,
        #                                                                                           second=0,
        #                                                                                           microsecond=0), \
        #                           timezone.datetime.fromtimestamp(end_date, tz=pytz.UTC).replace(hour=23, minute=59,
        #                                                                                          second=59,
        #                                                                                          microsecond=0)
        #     lookup_expr = LOOKUP_SEP.join(['timestamp', 'range'])
        #     timestamp_expr = {lookup_expr: (from_date, end_date)}
        #     filtered_queryset = queryset.filter(**timestamp_expr)

        commits_queryset = queryset.values('author_name', 'author_email', 'timestamp').order_by('author_name').annotate(
            ts=functions.TruncDay(models.F('timestamp'))).values('ts',
                                                                 'author_name', 'author_email').annotate(
            __count_day=models.Count('ts', distinct=True)).values('author_name', 'author_email', '__count_day').annotate(
            __count=models.Count('author_name'))

        filtered_commits_queryset = filtered_queryset.values('author_name', 'author_email', 'timestamp').order_by('author_name').annotate(
            ts=functions.TruncDay(models.F('timestamp'))).values('ts',
                                                                 'author_name', 'author_email').annotate(
            __count_day=models.Count('ts', distinct=True)).values('author_name', 'author_email', '__count_day').order_by('author_name').annotate(
            __count=models.Count('author_name'))

        filtered_output_queryset = filtered_queryset.values('author_name', 'author_email').annotate(
            sum_output=models.Sum('output')).values('author_name', 'author_email', 'sum_output')

        filtered_rework_queryset = filtered_queryset.values('author_name', 'author_email').annotate(
            sum_rework=models.Sum('rework')).values('author_name', 'author_email', 'sum_rework')

        filtered_defects_queryset = filtered_queryset.annotate(caused_defects__count=models.Count(
            models.Case(
                models.When(
                    models.Q(
                            caused_defects__isnull=False
                    ), then=models.F('caused_defects__id')
                )
            )
        )).values('author_name', 'author_email', 'caused_defects__count').exclude(caused_defects__count__lt=1)

        last_commit_queryset = filtered_queryset.values('author_name', 'author_email').annotate(last_timestamp=models.Max('timestamp')).values('author_name', 'author_email', 'last_timestamp')
        result_list = list()
        commits = {'{}\{}'.format(commit.get('author_name'), commit.get('author_email')): commit.get('__count') for commit in commits_queryset}
        filtered_output = {'{}\{}'.format(commit.get('author_name'), commit.get('author_email')): commit.get('sum_output') for commit in filtered_output_queryset}
        filtered_rework = {'{}\{}'.format(commit.get('author_name'), commit.get('author_email')): commit.get('sum_rework') for commit in filtered_rework_queryset}
        last_commit = {'{}\{}'.format(commit.get('author_name'), commit.get('author_email')): commit.get('last_timestamp') for commit in last_commit_queryset}
        filtered_defects = dict()
        for commit in filtered_defects_queryset:
            if filtered_defects.get('{}\{}'.format(commit.get('author_name'), commit.get('author_email'))):
                filtered_defects['{}\{}'.format(commit.get('author_name'), commit.get('author_email'))] += 1
            else:
                filtered_defects['{}\{}'.format(commit.get('author_name'), commit.get('author_email'))] = 1

        max_output = 0
        max_commits = 0
        avg = dict()

        for filtered_commit in filtered_commits_queryset:
            if not filtered_commit.get('author_name'):
                continue
            name = '{}\{}'.format(filtered_commit.get('author_name'), filtered_commit.get('author_email'))
            percent = float(filtered_commit.get('__count')) / commits.get(name)
            output_value = filtered_output.get(name) / filtered_commit.get(
                '__count_day') / percent
            avg_commits = float(filtered_commit.get('__count')) / filtered_commit.get('__count_day')
            rework_value = filtered_rework.get(name) / filtered_commit.get('__count')
            defects_value = filtered_defects.get(name) / float(
                filtered_commit.get('__count')) * 100 if filtered_defects.get(
                name) else 0
            max_output = output_value if output_value > max_output else max_output
            max_commits = avg_commits if avg_commits > max_commits else max_commits
            output_dict = {
                'username': filtered_commit.get('author_name'),
                'email': filtered_commit.get('author_email'),
                'timestamp_last_commit': last_commit.get(name),
                'output': output_value,
                'commits': avg_commits,
                'rework': rework_value,
                'defects': defects_value,
                '_count_commits': filtered_commit.get('__count'),
                '_count_day': filtered_commit.get('__count_day')
            }
            result_list.append(output_dict)

        avg['output'] = [user.get('output') for user in result_list if user.get('output') > 0]
        avg['commits'] = [user.get('commits') for user in result_list if user.get('commits') > 0]
        avg['defects'] = [user.get('defects') for user in result_list if user.get('defects') > 0]
        avg['rework'] = [user.get('rework') for user in result_list if user.get('rework') > 0]

        avg['output'] = sum(avg['output']) / len(avg['output']) if len(avg['output']) > 0 else 0
        avg['commits'] = sum(avg['commits']) / len(avg['commits']) if len(avg['commits']) > 0 else 0
        avg['defects'] = sum(avg['defects']) / len(avg['defects']) if len(avg['defects']) > 0 else 0
        avg['rework'] = sum(avg['rework']) / len(avg['rework']) if len(avg['rework']) > 0 else 0

        if request and 'ordering' in request.query_params:
            ordering_fields = request.query_params.get('ordering').split(',')
            if len(ordering_fields) == 1:
                if request.query_params.get('ordering')[0] == '-':
                    result_list = sorted(result_list, key=operator.itemgetter(request.query_params.get('ordering')[1:]),
                                         reverse=True)
                else:
                    result_list = sorted(result_list, key=operator.itemgetter(request.query_params.get('ordering')))

        page = self.paginate_queryset(result_list)

        data_serializer = {'users': page, 'avg': avg, 'max_output': max_output, 'max_commits': max_commits}
        if page is not None:
            serializer = self.get_serializer(data_serializer)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(data_serializer)
        return Response(serializer.data)
