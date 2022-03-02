# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.http import Http404
from django.shortcuts import get_object_or_404 as _get_object_or_404
from django.utils.translation import ugettext_lazy as _

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .serializers import *
from .filters import *


def get_object_or_404(queryset, *filter_args, **filter_kwargs):
    """
    Same as Django's standard shortcut, but make sure to also raise 404
    if the filter_kwargs don't match the required types.
    """
    try:
        return _get_object_or_404(queryset, *filter_args, **filter_kwargs)
    except (TypeError, ValueError):
        raise Http404


class StepModelViewSet(viewsets.ModelViewSet):
    model = Step
    queryset = Step.objects.all()

    serializer_class = StepSerializer
    filter_class = StepFilterSet

    ordering_fields = ()
    search_fields = ('^name',)
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'step_pk'

    def get_queryset(self):
        queryset = super(StepModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset


class TestModelViewSet(viewsets.ModelViewSet):
    """
    Test API endpoint
    ---
    list:
        List tests endpoint


    create:
        Create test endpoint


    retrieve:
        Retrieve test endpoint


    partial_update:
        Partial update test endpoint


    update:
        Update test endpoint


    changed:
        Changed list tests endpoint

    """
    model = Test
    queryset = Test.objects.select_related('project')
    serializer_class = TestSerializer
    filter_class = TestFilterSet

    ordering_fields = ('name',)
    search_fields = ()
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'test_pk'

    def get_queryset(self):
        queryset = super(TestModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset.order_by('name')

    @action(methods=['POST', ], detail=False, url_path=r'associate')
    def associate_tests(self, request, *args, **kwargs):
        files = request.data.get('files')
        areas = request.data.get('areas')
        tests = request.data.get('tests')

        serializer = TestAssociateSerializer(context={'tests': tests, 'files': files, 'areas': areas})
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['POST', ], detail=False, url_path=r'auto-associate')
    def auto_associate_tests(self, request, *args, **kwargs):
        tests = request.data.get('tests')
        queryset = super(TestModelViewSet, self).get_queryset()
        queryset = list(queryset.filter(id__in=tests))

        serializer = TestAssociateSerializer(context={'tests': queryset})
        serializer.auto_assign()

        return Response(serializer.data, status=status.HTTP_200_OK)


class TestTypeModelViewSet(viewsets.ModelViewSet):
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
    model = TestType
    queryset = TestType.objects.all()
    serializer_class = TestTypeSerializer
    filter_class = TestTypeFilterSet

    ordering_fields = ()
    search_fields = ('^name',)
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'test_type_pk'

    def get_queryset(self):
        queryset = super(TestTypeModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset


class TestSuiteModelViewSet(viewsets.ModelViewSet):
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
    model = TestSuite
    queryset = TestSuite.objects.select_related('project')
    serializer_class = TestSuiteSerializer
    filter_class = TestSuiteFilterSet

    search_fields = ()
    ordering_fields = ()
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'test_suite_pk'

    def get_queryset(self):
        queryset = super(TestSuiteModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset


class TestRunModelViewSet(viewsets.ModelViewSet):
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
    model = TestRun

    queryset = TestRun.objects.all()
    serializer_class = TestRunSerializer
    filter_class = TestRunFilterSet

    search_fields = ()
    ordering_fields = ('id', 'name', 'start_date',)
    filter_fields = ()  # ('project', 'is_local', 'type', )  # 'status',)

    lookup_field = 'pk'
    lookup_url_kwarg = 'test_run_pk'

    def get_queryset(self):
        queryset = super(TestRunModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset


class TestRunResultModelViewSet(viewsets.ModelViewSet):
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
    serializer_class = TestRunResultSerializer
    queryset = TestRunResult.objects.all()

    ordering_fields = ()
    search_fields = ()
    filter_class = TestRunResultFilterSet
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'test_run_result_pk'

    def get_queryset(self):
        queryset = super(TestRunResultModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset

    # @swagger_auto_schema(method='POST',
    #                      request_body=ImportTestingReportSerializer)  # , responses={201: OutputImportSerializer()})
    @action(methods=['POST', ], detail=False, url_path=r'import')
    def import_view(self, request, *args, **kwargs):

        serializer = ImportTestingReportSerializer(data=request.data, context={'request': request})
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


class DefectModelViewSet(viewsets.ModelViewSet):
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
    serializer_class = DefectSerializer
    queryset = Defect.objects.all()
    filter_class = DefectFilterSet

    search_fields = ('name',)
    ordering_fields = ()
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'defect_pk'

    def get_queryset(self):
        queryset = super(DefectModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))

        newest_test_run_results = TestRunResult.objects.filter(test=models.OuterRef('id')).order_by('-created')

        prefetch_passed_associated_tests = models.Prefetch(
            'associated_tests',
            queryset=Test.objects.annotate(
                current_test_run_results_status=models.Subquery(newest_test_run_results.values('status')[:1])
            ).filter(
                current_test_run_results_status=TestRunResult.STATUS_PASS
            ),
            to_attr='passed_associated_tests',
        )
        prefetch_failed_associated_tests = models.Prefetch(
            'associated_tests',
            queryset=Test.objects.annotate(
                current_test_run_results_status=models.Subquery(newest_test_run_results.values('status')[:1])
            ).filter(
                current_test_run_results_status=TestRunResult.STATUS_FAIL
            ),
            to_attr='failed_associated_tests',
        )

        prefetch_broken_associated_tests = models.Prefetch(
            'associated_tests',
            queryset=Test.objects.annotate(
                current_test_run_results_status=models.Subquery(newest_test_run_results.values('status')[:1])
            ).filter(
                current_test_run_results_status=TestRunResult.STATUS_BROKEN
            ),
            to_attr='broken_associated_tests',
        )

        prefetch_not_run_associated_tests = models.Prefetch(
            'associated_tests',
            queryset=Test.objects.annotate(
                current_test_run_results_status=models.Subquery(newest_test_run_results.values('status')[:1])
            ).filter(
                current_test_run_results_status__in=[
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

        return queryset

class NumberTestRunModelViewSet(viewsets.ModelViewSet):
    serializer_class = TestRunSerializer
    queryset = TestRun.objects.all()

    def get_queryset(self):
        queryset = TestRun.objects.filter(
            project_id=self.request.query_params.get('project_id'), 
            test_suite_id=self.request.query_params.get('test_suite_id')
        )
        return queryset