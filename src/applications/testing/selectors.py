# -*- coding: utf-8 -*-
import logging
import time
from datetime import timedelta, date
import gc
import pathlib
from django.db import models
from django.db.models import Q, F, Count, Value, CharField, Subquery, OuterRef
from django.db.models.functions import Concat, Coalesce
from django.utils import timezone
from django.conf import settings
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.db.models import Count
from django.db.models.expressions import *
from django.db.models.lookups import GreaterThan
from django.db.models.functions import *
import re
from nltk.stem import PorterStemmer

from rest_framework_filters import FilterSet

from applications.integration.ssh_v2.tasks import fetch_commits_task_v2
from applications.integration.ssh_v2.utils import prioritize_task

from applications.testing.models import Test, TestRun, TestSuite, TestRunResult, Defect
from applications.vcs.models import Commit, Area, Branch
from applications.vcs.utils.analysis import calculate_user_analysis, calculate_user_analysis_by_range, \
    avg_per_range, calculate_similar_by_commit
from applications.ml.models import MLModel
from system.celery_app import app


LOOKUP_SEP = '__'


TEST_RUNS_ML_USING_THRESHOLD = 100
MINIMAL_NUMBER_OF_TESTRUNS_FOR_ML_MODEL_USING = 10


class Priority(models.IntegerChoices):
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    UNASSIGNED = 4
    RERUN = 5
    READY_DEFECT = 6
    OPEN_DEFECT = 7
    TOP20 = 8
    PERCENT = 9
    FOR_TEST = 10
    FOR_TEST_WITH_DAY = 11
    EXECUTION_TIME_UNDER = 12


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


def prioritized_test_list(*, params=None):
    params = params or {}

    use_sql = False
    test_suite = params["test_suite"]

    commit_list = get_commit_list(params=params)
    commit_queryset = Commit.objects.filter(id__in=set(commit_list))

    commit_queryset_sha = commit_queryset.values_list("sha", flat=True)

    try:
        prioritize_task(commits_sha=commit_queryset_sha)
    except Exception as exc:
        logging.exception(f"Error with 'prioritize_task'", exc_info=True)

    # while True:
    #     fully_processed = True
    #     for commit in commit_queryset:
    #         if not commit.is_processed:
    #             fully_processed = False
    #             break
    #     if fully_processed:
    #         break

    test_run_count = TestRun.objects.filter(test_suite=test_suite).count()

    queryset = Test.objects.filter(
        project=params["project"]
    )
    if test_suite:
        queryset = queryset.filter(test_suites=test_suite)

    ml_predictor = None
    if test_suite:
        ml_predictor = MLModel.load_model(test_suite_id=test_suite.id)

    ml_model_existing_flag = ml_predictor is not None

    if ml_model_existing_flag is False or test_run_count < MINIMAL_NUMBER_OF_TESTRUNS_FOR_ML_MODEL_USING:
        use_sql = True

    priority = params["priority"]
    keyword = params.get("keyword", None)

    logging.info(f"Get priority tests with params: {params} - use SQL: {use_sql}")

    if priority == PRIORITY_HIGH:
        if use_sql:
            queryset = get_default_high_queryset(queryset, commit_list, params=params)
        else:
            if test_run_count >= TEST_RUNS_ML_USING_THRESHOLD:
                test_ids = ml_predictor.predict_by_priority(queryset, commit_queryset, keyword=keyword)['high']
                queryset = queryset.filter(id__in=test_ids).distinct('name')
            else:
                ml_prediction_results = ml_predictor.predict_by_priority(queryset, commit_queryset, keyword=keyword)
                ml_unassigned_tests_num = len(ml_prediction_results['unassigned'])
                original_unassigned_num = get_default_unassigned_queryset(queryset, params=params).count()
                if original_unassigned_num > ml_unassigned_tests_num:
                    test_ids = ml_prediction_results['high']
                    queryset = queryset.filter(id__in=test_ids).distinct('name')
                else:
                    queryset = get_default_high_queryset(queryset, commit_list, params=params)

    elif priority == PRIORITY_MEDIUM:
        if use_sql:
            queryset = get_default_medium_queryset(queryset, commit_list, params=params)
        else:
            if test_run_count >= TEST_RUNS_ML_USING_THRESHOLD:
                test_ids = ml_predictor.predict_by_priority(queryset, commit_queryset, keyword=keyword)['medium']
                queryset = queryset.filter(id__in=test_ids).distinct('name')
            else:
                ml_prediction_results = ml_predictor.predict_by_priority(queryset, commit_queryset, keyword=keyword)
                ml_unassigned_tests_num = len(ml_prediction_results['unassigned'])
                original_unassigned_num = get_default_unassigned_queryset(queryset, params=params).count()
                if original_unassigned_num > ml_unassigned_tests_num:
                    test_ids = ml_prediction_results['medium']
                    queryset = queryset.filter(id__in=test_ids).distinct('name')
                else:
                    queryset = get_default_medium_queryset(queryset, commit_list, params=params)

    elif priority == PRIORITY_LOW:
        if use_sql:
            queryset = get_default_low_queryset(queryset, commit_list, params=params)
        else:
            if test_run_count >= TEST_RUNS_ML_USING_THRESHOLD:
                test_ids = ml_predictor.predict_by_priority(queryset, commit_queryset, keyword=keyword)['low']
                queryset = queryset.filter(id__in=test_ids).distinct('name')
            else:
                ml_prediction_results = ml_predictor.predict_by_priority(queryset, commit_queryset, keyword=keyword)
                ml_unassigned_tests_num = len(ml_prediction_results['unassigned'])
                original_unassigned_num = get_default_unassigned_queryset(queryset, params=params).count()
                if original_unassigned_num > ml_unassigned_tests_num:
                    test_ids = ml_prediction_results['low']
                    queryset = queryset.filter(id__in=test_ids).distinct('name')
                else:
                    queryset = get_default_low_queryset(queryset, commit_list, params=params)

    elif priority == PRIORITY_UNASSIGNED:
        queryset = get_default_unassigned_queryset(queryset, params=params)

    elif priority == PRIORITY_READY_DEFECT:
        queryset = get_default_ready_defect_queryset(queryset, params=params)

    elif priority == PRIORITY_OPEN_DEFECT:
        queryset = get_default_open_defect_queryset(queryset, params=params)

    elif priority == PRIORITY_RERUN:
        queryset = get_default_rerun_queryset(queryset, test_run=None, params=params)

    elif priority == PRIORITY_TOP20:
        params["percent"] = 20
        if use_sql:
            queryset = get_default_top20_queryset(queryset, commit_list, percent=params["percent"], params=params)
        else:
            if test_run_count >= TEST_RUNS_ML_USING_THRESHOLD:
                test_ids = ml_predictor.predict_by_percent(queryset, commit_queryset, keyword=keyword,
                                                           percent=params.get("percent", 20))
                queryset = queryset.filter(id__in=test_ids).distinct('name')
            else:
                queryset = get_default_top20_queryset(queryset, commit_list, percent=params["percent"], params=params)

    elif priority == PRIORITY_PERCENT:
        if use_sql:
            queryset = get_default_by_percent_queryset(queryset, commit_list, percent=params["percent"], params=params)
        else:
            if test_run_count >= TEST_RUNS_ML_USING_THRESHOLD:
                test_ids = ml_predictor.predict_by_percent(queryset, commit_queryset, keyword=keyword,
                                                           percent=params.get("percent"))
                queryset = queryset.filter(id__in=test_ids).distinct('name')
            else:
                queryset = get_default_by_percent_queryset(
                    queryset, commit_list, percent=params["percent"], params=params)

    elif priority == PRIORITY_FOR_TEST or priority == PRIORITY_FOR_TEST_WITH_DAY:
        queryset = get_default_all_queryset(queryset, params=params)

    elif priority == PRIORITY_EXECUTION_TIME_UNDER:
        queryset = get_default_highest_tests_under_time(queryset, params=params)

    classname = params.get("classname", False)
    if classname:
        classname_separator = params.get("classname_separator", "")
        queryset = queryset.annotate(mname=F('name')).values('mname').annotate(name=Concat(F('class_name'), Value(classname_separator), 'mname', output_field=CharField())).values('name')

    testsuitename = params.get("testsuitename", False)
    if testsuitename:
        testsuitename_separator = params.get("testsuitename_separator", "")
        queryset = queryset.annotate(mname=F('name')).values('mname').annotate(name=Concat(F('area__name'), Value(testsuitename_separator), 'mname', output_field=CharField())).values('name')

    return queryset


def get_last_run_result_commit(project=None, target_branch=None, test_suite=None, commit=None, **kwargs):
    """
    Return last commit of commits set that has 'target_branch' in 'branches' and have test runs.

    If no one commit will be found we raise exception

    :param project: py:obj:`Project` object
    :param target_branch: py:obj:`Branch` object
    :param test_suite: py:obj:`TestSuite` object
    :return: py:obj:`Commit` object or may raise NotFound exception
    """
    time_threshold = commit.timestamp - timezone.timedelta(days=1)
    last_run_commit_list = Commit.objects.filter(project=project,
                                                 branches=target_branch,
                                                 test_runs__isnull=False,
                                                 test_runs__test_suite=test_suite,
                                                 timestamp__gt=time_threshold,
                                                 timestamp__lt=commit.timestamp).order_by('-timestamp')

    if not last_run_commit_list.first():
        last_run_commit_list = Commit.objects.filter(project=project,
                                                     branches=target_branch,
                                                     timestamp__gt=time_threshold,
                                                     timestamp__lt=commit.timestamp).order_by('-timestamp')
        if not last_run_commit_list.first():
            return commit
    return last_run_commit_list.first()


def get_commit_range_list(target_branch=None, first_commit=None, second_commit=None, exclusive=False, **kwargs):
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
    return list(target_branch.commits.filter(query).values_list('id', flat=True))


def get_commit_list(*, params=None):
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
    commit_list = []
    commit_type = params["commit_type"]
    commit = params["commit"]
    if commit_type == "Single":
        commit_list = [commit.id]
    elif commit_type == "LastRun":
        second_commit = get_last_run_result_commit(**params)
        commit_list = get_commit_range_list(
            target_branch=params["target_branch"],
            first_commit=params["commit"],
            second_commit=second_commit
        )
    elif commit_type in ["BetweenInclusive", "BetweenExclusive"]:
        exclusive = False
        if commit_type == "BetweenExclusive":
            exclusive = True
        commit_list = get_commit_range_list(
            target_branch=params["target_branch"],
            first_commit=params["commit"],
            second_commit=params["from_commit"],
            exclusive=exclusive
        )
    return commit_list


def get_default_high_queryset(queryset, commits_ids, params=None):
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
        filechange__file_id=F('project__commits__filechange__file_id'),
    ).filter(
        associated_defects__type=Defect.TYPE_PROJECT,
        associated_defects__status=Defect.STATUS_CLOSED,
        associated_defects__close_type__in=[Defect.CLOSE_TYPE_FIXED, Defect.CLOSE_TYPE_WONT_FIX],
        filechange__file_id=F('associated_defects__caused_by_commits__filechange__file_id')
    )
    high_priority_query = Q(id__in=file_query_set.values_list('id', flat=True))
    high_priority_query |= Q(id__in=queryset.values_list('id', flat=True))
    qs = Test.objects.filter(high_priority_query)
    qs = qs.distinct('name')
    return qs


def get_default_medium_queryset(queryset, commits_ids, params=None):
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
    # qs = queryset
    # area_query_set = qs.filter(Q(associated_areas__isnull=False))
    # commits_areas = list(Commit.objects.filter(id__in=commits_ids).values_list('areas', flat=True))
    # depended_areas_annotations = {
    #     'depended_area_lvl%d' % i: F('associated_areas'+(LOOKUP_SEP+'dependencies')*i) for i in range(1, 6)}
    # area_query_set = area_query_set.annotate(**depended_areas_annotations)
    # area_query_filter = Q(associated_areas__in=commits_areas)
    # for depended_area_level in depended_areas_annotations.keys():
    #     area_query_filter |= Q(**{LOOKUP_SEP.join([depended_area_level, 'in']): commits_areas})
    # area_query_set = area_query_set.filter(area_query_filter)
    #
    # qs = qs.filter(project__commits__id__in=commits_ids)
    # qs = qs.filter(
    #     associated_defects__type=Defect.TYPE_PROJECT,
    #     associated_defects__status=Defect.STATUS_CLOSED,
    #     associated_defects__close_type__in=[Defect.CLOSE_TYPE_FIXED, Defect.CLOSE_TYPE_WONT_FIX],
    # )
    #
    # default_area_id = Area.get_default(project=params['project']).id
    # qs = qs.annotate(
    #     commit__areas=F('project__commits__areas'),
    #     caused_by_commits__areas=F('associated_defects__caused_by_commits__areas')
    # ).filter(
    #     ~Q(commit__areas=default_area_id) &
    #     Q(Q(commit__areas=F('caused_by_commits__areas')) | Q(commit__areas=F('area')))
    # )
    # medium_query = Q(id__in=area_query_set.values_list('id', flat=True))
    # medium_query |= Q(id__in=qs.values_list('id', flat=True))
    #
    # high_queryset = get_default_high_queryset(queryset, commits_ids, params=params)
    # exclude_test_ids = set(list(high_queryset.values_list('id', flat=True)))
    # qs = Test.objects.exclude(id__in=exclude_test_ids).filter(medium_query)
    # qs = qs.distinct('name')
    project = params['project']
    test_suite = params['test_suite']

    default_area_id = Area.get_default(project=project).id
    commits_areas_ids = list(Commit.objects.filter(id__in=commits_ids).values_list('areas__id', flat=True))

    pre_qs = Test.objects.raw("""
    SELECT
  "testing_test"."id" as "id"
FROM
  "testing_test"
WHERE
  (
    "testing_test"."id" IN (
      with recursive vcs_area_dependency_graph as (
        select
          1 as level,
          d.from_area_id,
          d.to_area_id,
          array[d.from_area_id] as all_parents
        from
          vcs_area_dependencies d
        where
          from_area_id = ANY(%(commits_areas_ids)s)
        union all
        select
          t.level + 1 as level,
          d.from_area_id,
          d.to_area_id,
          t.all_parents || d.from_area_id
        from
          vcs_area_dependency_graph t
          inner join vcs_area_dependencies d on t.to_area_id = d.from_area_id
          and d.to_area_id <> ALL (t.all_parents)
        where
          t.level <= 4
      )
      SELECT
        U0."id"
      FROM
        "testing_test" U0
        inner join "testing_testsuite_tests" U2 ON (U0."id" = U2."test_id")
        inner join "testing_test_associated_areas" U4 ON (U0."id" = U4."test_id")
        inner join "vcs_area" U5 ON (U4."area_id" = U5."id")
        left outer join "testing_test_associated_areas" U16 ON (U0."id" = U16."test_id")
      WHERE
        (
          U0."project_id" = %(project_id)s
          AND U2."testsuite_id" = %(testsuite_id)s
          AND U4."area_id" IS NOT NULL
          AND (
            U16."area_id" = ANY(%(commits_areas_ids)s)
            OR U5.id IN (
              SELECT
                to_area_id
              FROM
                vcs_area_dependency_graph
            )
          )
        )
      group by
        1
    )
    OR "testing_test"."id" IN (
      SELECT
        U0."id"
      FROM
        "testing_test" U0
        inner join "project_project" U1 ON (U0."project_id" = U1."id")
        inner join "testing_testsuite_tests" U2 ON (U0."id" = U2."test_id")
        inner join "vcs_commit" U4 ON (U1."id" = U4."project_id")
        inner join "testing_defect_associated_tests" U5 ON (U0."id" = U5."test_id")
        inner join "testing_defect" U6 ON (U5."defect_id" = U6."id")
        left outer join "vcs_commit_areas" U7 ON (U4."id" = U7."commit_id")
        left outer join "testing_defect_caused_by_commits" U9 ON (U6."id" = U9."defect_id")
        left outer join "vcs_commit" U10 ON (U9."commit_id" = U10."id")
        left outer join "vcs_commit_areas" U11 ON (U10."id" = U11."commit_id")
      WHERE
        (
          U0."project_id" = %(project_id)s
          AND U2."testsuite_id" = %(testsuite_id)s
          AND U4."id" = ANY(%(commits_ids)s)
          AND U6."close_type" IN (1, 3)
          AND U6."status" = 4
          AND U6."type" = 3
          AND NOT (U7."area_id" = %(default_area_id)s)
          AND (
            U7."area_id" = U11."area_id"
            OR U7."area_id" = U0."area_id"
          )
        )
    )
  )

    """, params={
        'project_id': project.id,
        'testsuite_id': test_suite.id,
        'default_area_id': default_area_id,
        'commits_areas_ids': commits_areas_ids,
        'commits_ids': commits_ids
    })
    qs = Test.objects.filter(id__in=[item.id for item in pre_qs])
    qs = qs.distinct('name')
    # print(qs.query)
    return qs


def get_default_unassigned_queryset(queryset, params=None):
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
    qs = queryset
    exclude_test_ids = Test.objects.filter(
        associated_defects__type=Defect.TYPE_PROJECT
    ).values_list('id', flat=True)
    qs = qs.exclude(id__in=exclude_test_ids)
    qs = qs.exclude(Q(associated_files__isnull=False) | Q(associated_areas__isnull=False))
    qs = qs.distinct('name')
    return qs


def get_default_low_queryset(queryset, commits_ids, params=None):
    qs = queryset

    exclude_test_ids = set(list(get_default_medium_queryset(queryset, commits_ids, params=params).values_list('id', flat=True)))
    qs = qs.exclude(id__in=exclude_test_ids)

    exclude_test_ids = set(list(get_default_unassigned_queryset(queryset, params=params).values_list('id', flat=True)))
    qs = qs.exclude(id__in=exclude_test_ids)
    qs = qs.distinct('name')
    return qs


def get_default_ready_defect_queryset(queryset, params=None):
    qs = queryset
    qs = qs.filter(test_suites__test_runs__commit=params["commit"])

    exclude_test_ids = set(list(get_default_open_defect_queryset(queryset, params=params).values_list('id', flat=True)))
    qs = qs.exclude(id__in=exclude_test_ids)

    qs = qs.filter(
        associated_defects__type__not_in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL],
        associated_defects__status=Defect.STATUS_READY,
    )
    return qs.distinct('name')


def get_default_open_defect_queryset(queryset, params=None):
    qs = queryset
    qs = qs.filter(test_suites__test_runs__commit=params["commit"])

    qs = qs.filter(
        associated_defects__type__not_in=[Defect.TYPE_FLAKY, Defect.TYPE_ENVIRONMENTAL],
        associated_defects__status__in=[Defect.STATUS_IN_PROGRESS, Defect.STATUS_VERIFIED],
    )
    return qs.distinct('name')


def get_default_rerun_queryset(queryset, test_run=None, params=None):
    qs = queryset

    commit = params["commit"]

    qs = qs.filter(test_suites__test_runs__commit=commit)

    newest_test_run = TestRun.objects.filter(
        id__in=set(list(qs.values_list('test_runs__id', flat=True)))).order_by('-created').first()

    if test_run:
        newest_test_run = TestRun.objects.get(id=test_run.id)

    newest_current_test_run_results = TestRunResult.objects.filter(test_run=newest_test_run, test=OuterRef('id'))
    newest_current_test_run_results = newest_current_test_run_results.filter(commit_id=commit.id)

    newest_current_test_run_results = newest_current_test_run_results.annotate(
        __count=Coalesce(Count('*'), 0)).order_by('-created')

    qs = qs.annotate(
        runtest_result_count=Subquery(newest_current_test_run_results.values('__count')[:1]),
        current_status=Subquery(newest_current_test_run_results.values('status')[:1])
    ).filter(
        runtest_result_count=1,
        current_status__in=[TestRunResult.STATUS_FAIL, TestRunResult.STATUS_BROKEN, TestRunResult.STATUS_ERROR]
    )
    return qs.distinct('name')


def get_default_top20_queryset(queryset, commits_ids, percent=20, params=None):
    return get_default_by_percent_queryset(queryset=queryset, commits_ids=commits_ids, percent=20, params=params)


def get_default_by_percent_queryset(queryset, commits_ids, percent, params=None):
    qs = queryset

    commit = params["commit"]
    result = calculate_score(test_queryset=queryset, commit_id=commit.id)

    test_ids = list(result.keys())

    _count = len(test_ids)
    _per = int(_count * (percent / 100))
    _ids = test_ids[:_per]

    qs = Test.objects.filter(id__in=_ids)
    return qs.distinct('name')


def get_default_all_queryset(queryset, params=None):
    """
    This function returns all tests queryset.

    :param queryset:
    :return queryset:
    """
    qs = queryset
    priority = params["priority"]
    day = params["day"]
    if day is not None and int(priority) == 11:
        try:
            day_val = int(day)
            if day_val < 0:
                raise Exception('Please enter a valid number of days.')
        except ValueError:
            raise Exception('Please enter a valid number of days.')
        to_date = timezone.now()
        from_date = to_date - timezone.timedelta(days=day_val)
        qs = qs.filter(created__range=(from_date, to_date))
    return qs.distinct('name')


def get_default_highest_tests_under_time(queryset, params=None):
    """
    This function returns the highest tests set under time in minutes
    """
    qs = queryset
    time = params["time"]
    if time is not None:
        time = int(time)
        qs = qs.order_by('-priority')
        id_set = set()
        for test in qs:
            testrunresult_set = TestRunResult.objects.filter(test=test).filter(status='pass').order_by('execution_started')
            last_pass = testrunresult_set.first()
            if last_pass is not None:
                if last_pass.execution_time < time*60:
                    id_set.add(last_pass.id)
                else:
                    break
            else:
                continue
        qs = qs.filter(id__in=id_set)
        return qs.distinct('name')
    else:
        raise Exception('Time is required in minute(s).')


class TestRunReportFilterSet(FilterSet):

    # test_run_type = NumberFilter(field_name='test_run_type')
    # status = NumberFilter(field_name='test_run_status')
    # is_local = BooleanFilter(field_name='is_local')

    class Meta(object):
        model = TestRun
        fields = ('project', 'test_suite', 'type', 'status', 'is_local')


def test_run_report_list(*, filters=None):
    """
    'project', 'test_suite', 'test_run_type', 'status', 'is_local'

    params = {
        'organization': Organization(),
        'project': Project(),
        'test_suite': TestSuite() | None,
        'test_run_type': 1 | 2 | 3 | None,
        'status': 1 | 2 | 3 | None,
        'is_local': True | False,
    }

    """
    filters = filters or {}

    class BaseTestRunFilter(FilterSet):
        class Meta:
            model = TestRun
            fields = ('project', 'test_suite', 'type', 'status', 'is_local')

    queryset = TestRun.objects.all()
    queryset = BaseTestRunFilter(filters, queryset).qs

    queryset = queryset.extra(
        select={
            'created_defect_count': """
                    SELECT COUNT(*) AS created_defects_count
                    FROM testing_defect
                    WHERE
                    testing_defect.project_id = testing_testrun.project_id
                    AND testing_defect.created_by_test_run_id = testing_testrun.id
                    """,
            'founded_defect_count': """
                    SELECT COUNT(*) AS founded_defects_flaky_failure_count
                    FROM testing_defect
                    INNER JOIN testing_testrunresult ON testing_testrunresult.id = testing_defect.created_by_test_run_result_id
                    WHERE
                    testing_defect.project_id = testing_testrun.project_id
                    AND testing_defect."type" IN (2, 4, 1)
                    AND testing_defect.created_by_test_run_id = testing_testrun.id
                    AND testing_testrunresult.test_run_id = testing_testrun.id
                    """,
            'previous_test_run_execution_time': """
                    SELECT COALESCE(SUM("execution_time"), 0) as execution_time
                    FROM testing_testrunresult
                    WHERE testing_testrunresult.test_run_id = testing_testrun.previous_test_run_id
                    """
        }
    )

    queryset = queryset.annotate(
        _project=JSONObject(id='project__id', name='project__name'),
        _test_suite=JSONObject(id='test_suite__id', name='test_suite__name'),
        _start_date=TruncSecond(models.F('start_date')),
        _end_date=models.Case(
            models.When(
                ~models.Q(end_date=None),
                then=TruncSecond(models.F('end_date'))
            )
        ),
        tests__execution_time=models.Case(
            models.When(models.Q(mv_test_count_by_type__isnull=False),
                        then=models.F('mv_test_count_by_type__execution_time')),
            default=Value(0.0)
        ),
        # _previous_execution_time=models.F('previous_test_run_execution_time'),
        tests__count=models.Case(
            models.When(models.Q(mv_test_count_by_type__isnull=False),
                        then=models.F('mv_test_count_by_type__tests_count')),
            default=Value(0)
        ),
        passed_tests__count=models.Case(
            models.When(models.Q(mv_test_count_by_type__isnull=False),
                        then=models.F('mv_test_count_by_type__passed_tests_count')),
            default=Value(0)
        ),
        failed_tests__count=models.Case(
            models.When(models.Q(mv_test_count_by_type__isnull=False),
                        then=models.F('mv_test_count_by_type__failed_tests_count')),
            default=Value(0)
        ),
        broken_tests__count=models.Case(
            models.When(models.Q(mv_test_count_by_type__isnull=False),
                        then=models.F('mv_test_count_by_type__broken_tests_count')),
            default=Value(0)
        ),
        not_run_tests__count=models.Case(
            models.When(models.Q(mv_test_count_by_type__isnull=False),
                        then=models.F('mv_test_count_by_type__not_run_tests_count')),
            default=Value(0)
        ),
        tests_failure_sum=models.F('failed_tests__count') + models.F('broken_tests__count'),
        tests__status=models.Case(
            models.When(
                tests_failure_sum__gt=0,
                then=Value('Failure')),
            default=Value('Passed')
        )
    )
    return queryset


def camel_case_split(str):
    return re.sub(r'((?<=[a-z])[A-Z]|(?<!\A)[A-Z](?=[a-z]))', r' \1', str)


def non_alpha_split(str):
    str = camel_case_split(str)
    return re.split('[^a-zA-Z]', str)


def common_elements(list1, list2):
    result = []
    for element in list1:
        if element in list2:
            result.append(element)
    return result


def number_common_elements(list1, list2):
    count = 0
    for element in list1:
        if element in list2:
            count = count + 1
    return count


def get_tokens_from_list(list):
    #use library for stopworks rather than this
    ps = PorterStemmer()
    tokens = []
    stop_words = ["0o", "0s", "3a", "3b", "3d", "6b", "6o", "a", "a1", "a2", "a3", "a4", "ab", "able",
                  "about", "above", "abst", "ac", "accordance", "according", "accordingly", "across",
                  "act", "actually", "ad", "added", "adj", "ae", "af", "affected", "affecting", "affects",
                  "after", "afterwards", "ag", "again", "against", "ah", "ain", "ain't", "aj", "al", "all",
                  "allow", "allows", "almost", "alone", "along", "already", "also", "although", "always", "am",
                  "among", "amongst", "amoungst", "amount", "an", "and", "announce", "another", "any",
                  "anybody", "anyhow", "anymore", "anyone", "anything", "anyway", "anyways", "anywhere", "ao", "ap",
                  "apart", "apparently", "appear", "appreciate", "appropriate", "approximately", "ar", "are", "aren",
                  "arent", "aren't", "arise", "around", "as", "a's", "aside", "ask", "asking", "associated", "at",
                  "au", "auth", "av", "available", "aw", "away", "awfully", "ax", "ay", "az", "b", "b1", "b2",
                  "b3", "ba", "back", "bc", "bd", "be", "became", "because", "become", "becomes", "becoming",
                  "been", "before", "beforehand", "begin", "beginning", "beginnings", "begins", "behind", "being",
                  "believe", "below", "beside", "besides", "best", "better", "between", "beyond", "bi", "bill",
                  "biol", "bj", "bk", "bl", "bn", "both", "bottom", "bp", "br", "brief", "briefly", "bs", "bt",
                  "bu", "but", "bx", "by", "c", "c1", "c2", "c3", "ca", "call", "came", "can", "cannot", "cant",
                  "can't", "cause", "causes", "cc", "cd", "ce", "certain", "certainly", "cf", "cg", "ch", "changes",
                  "ci", "cit", "cj", "cl", "clearly", "cm", "c'mon", "cn", "co", "com", "come", "comes",
                  "con", "concerning", "consequently", "consider", "considering", "contain", "containing",
                  "contains", "corresponding", "could", "couldn", "couldnt", "couldn't", "course", "cp", "cq",
                  "cr", "cry", "cs", "c's", "ct", "cu", "currently", "cv", "cx", "cy", "cz", "d", "d2", "da",
                  "date", "dc", "dd", "de", "definitely", "describe", "described", "despite", "detail", "df",
                  "di", "did", "didn", "didn't", "different", "dj", "dk", "dl", "do", "does", "doesn", "doesn't",
                  "doing", "don", "done", "don't", "down", "downwards", "dp", "dr", "ds", "dt", "du", "due",
                  "during", "dx", "dy", "e", "e2", "e3", "ea", "each", "ec", "ed", "edu", "ee", "ef", "effect",
                  "eg", "ei", "eight", "eighty", "either", "ej", "el", "eleven", "else", "elsewhere", "em",
                  "empty", "en", "end", "ending", "enough", "entirely", "eo", "ep", "eq", "er", "es", "especially",
                  "est", "et", "et-al", "etc", "eu", "ev", "even", "ever", "every", "everybody", "everyone",
                  "everything", "everywhere", "ex", "exactly", "example", "except", "ey", "f", "f2", "fa",
                  "far", "fc", "few", "ff", "fi", "fifteen", "fifth", "fify", "fill", "find", "fire", "first",
                  "five", "fix", "fj", "fl", "fn", "fo", "followed", "following", "follows", "for", "former",
                  "formerly", "forth", "forty", "found", "four", "fr", "from", "front", "fs", "ft", "fu", "full",
                  "further", "furthermore", "fy", "g", "ga", "gave", "ge", "get", "gets", "getting", "gi", "give",
                  "given", "gives", "giving", "gj", "gl", "go", "goes", "going", "gone", "got", "gotten", "gr",
                  "greetings", "gs", "gy", "h", "h2", "h3", "had", "hadn", "hadn't", "happens", "hardly", "has",
                  "hasn", "hasnt", "hasn't", "have", "haven", "haven't", "having", "he", "hed", "he'd", "he'll",
                  "hello", "help", "hence", "her", "here", "hereafter", "hereby", "herein", "heres", "here's",
                  "hereupon", "hers", "herself", "hes", "he's", "hh", "hi", "hid", "him", "himself", "his",
                  "hither", "hj", "ho", "home", "hopefully", "how", "howbeit", "however", "how's", "hr", "hs",
                  "http", "hu", "hundred", "hy", "i", "i2", "i3", "i4", "i6", "i7", "i8", "ia", "ib",
                  "ibid", "ic", "id", "i'd", "ie", "if", "ig", "ignored", "ih", "ii", "ij", "il", "i'll", "im",
                  "i'm", "immediate", "immediately", "importance", "important", "in", "inasmuch", "inc",
                  "indeed", "index", "indicate", "indicated", "indicates", "information", "inner", "insofar",
                  "instead", "interest", "into", "invention", "inward", "io", "ip", "iq", "ir", "is", "isn",
                  "isn't", "it", "itd", "it'd", "it'll", "its", "it's", "itself", "iv", "i've", "ix", "iy",
                  "iz", "j", "jj", "jr", "js", "jt", "ju", "just", "k", "ke", "keep", "keeps", "kept", "kg",
                  "kj", "km", "know", "known", "knows", "ko", "l", "l2", "la", "largely", "last", "lately",
                  "later", "latter", "latterly", "lb", "lc", "le", "least", "les", "less", "lest", "let",
                  "lets", "let's", "lf", "like", "liked", "likely", "line", "little", "lj", "ll", "ll",
                  "ln", "lo", "look", "looking", "looks", "los", "lr", "ls", "lt", "ltd", "m", "m2",
                  "ma", "made", "mainly", "make", "makes", "many", "may", "maybe", "me", "mean", "means",
                  "meantime", "meanwhile", "merely", "mg", "might", "mightn", "mightn't", "mill", "million",
                  "mine", "miss", "ml", "mn", "mo", "more", "moreover", "most", "mostly", "move", "mr",
                  "mrs", "ms", "mt", "mu", "much", "mug", "must", "mustn", "mustn't", "my", "myself", "n",
                  "n2", "na", "name", "namely", "nay", "nc", "nd", "ne", "near", "nearly", "necessarily",
                  "necessary", "need", "needn", "needn't", "needs", "neither", "never", "nevertheless",
                  "new", "next", "ng", "ni", "nine", "ninety", "nj", "nl", "nn", "no", "nobody", "non",
                  "none", "nonetheless", "noone", "nor", "normally", "nos", "not", "noted", "nothing",
                  "novel", "now", "nowhere", "nr", "ns", "nt", "ny", "o", "oa", "ob", "obtain", "obtained",
                  "obviously", "oc", "od", "of", "off", "often", "og", "oh", "oi", "oj", "ok", "okay", "ol",
                  "old", "om", "omitted", "on", "once", "one", "ones", "only", "onto", "oo", "op", "oq", "or", "ord",
                  "os", "ot", "other", "others", "otherwise", "ou", "ought", "our", "ours", "ourselves", "out",
                  "outside", "over", "overall", "ow", "owing", "own", "ox", "oz", "p", "p1", "p2", "p3", "page",
                  "pagecount", "pages", "par", "part", "particular", "particularly", "pas", "past", "pc", "pd",
                  "pe", "per", "perhaps", "pf", "ph", "pi", "pj", "pk", "pl", "placed", "please", "plus", "pm",
                  "pn", "po", "poorly", "possible", "possibly", "potentially", "pp", "pq", "pr", "predominantly",
                  "present", "presumably", "previously", "primarily", "probably", "promptly", "proud", "provides",
                  "ps", "pt", "pu", "put", "py", "q", "qj", "qu", "que", "quickly", "quite", "qv", "r", "r2",
                  "ra", "ran", "rather", "rc", "rd", "re", "readily", "really", "reasonably", "recent",
                  "recently", "ref", "refs", "regarding", "regardless", "regards", "related", "relatively",
                  "research", "research-articl", "respectively", "resulted", "resulting", "results", "rf",
                  "rh", "ri", "right", "rj", "rl", "rm", "rn", "ro", "rq", "rr", "rs", "rt", "ru", "run",
                  "rv", "ry", "s", "s2", "sa", "said", "same", "saw", "say", "saying", "says", "sc", "sd",
                  "se", "sec", "second", "secondly", "section", "see", "seeing", "seem", "seemed", "seeming",
                  "seems", "seen", "self", "selves", "sensible", "sent", "serious", "seriously", "seven",
                  "several", "sf", "shall", "shan", "shan't", "she", "shed", "she'd", "she'll", "shes",
                  "she's", "should", "shouldn", "shouldn't", "should've", "show", "showed", "shown",
                  "showns", "shows", "si", "side", "significant", "significantly", "similar", "similarly",
                  "since", "sincere", "six", "sixty", "sj", "sl", "slightly", "sm", "sn", "so", "some",
                  "somebody", "somehow", "someone", "somethan", "something", "sometime", "sometimes", "somewhat",
                  "somewhere", "soon", "sorry", "sp", "specifically", "specified", "specify", "specifying",
                  "sq", "sr", "ss", "st", "still", "stop", "strongly", "sub", "substantially", "successfully",
                  "such", "sufficiently", "suggest", "sup", "sure", "sy", "system", "sz", "t", "t1", "t2",
                  "t3", "take", "taken", "taking", "tb", "tc", "td", "te", "tell", "ten", "tends", "tf",
                  "th", "than", "thank", "thanks", "thanx", "that", "that'll", "thats", "that's", "that've",
                  "the", "their", "theirs", "them", "themselves", "then", "thence", "there", "thereafter",
                  "thereby", "thered", "therefore", "therein", "there'll", "thereof", "therere", "theres",
                  "there's", "thereto", "thereupon", "there've", "these", "they", "theyd", "they'd", "they'll",
                  "theyre", "they're", "they've", "thickv", "thin", "think", "third", "this", "thorough",
                  "thoroughly", "those", "thou", "though", "thoughh", "thousand", "three", "throug",
                  "through", "throughout", "thru", "thus", "ti", "til", "tip", "tj", "tl", "tm", "tn", "to",
                  "together", "too", "took", "top", "toward", "towards", "tp", "tq", "tr", "tried", "tries",
                  "truly", "try", "trying", "ts", "t's", "tt", "tv", "twelve", "twenty", "twice", "two", "tx",
                  "u", "u201d", "ue", "ui", "uj", "uk", "um", "un", "under", "unfortunately", "unless", "unlike", "unlikely", "until", "unto", "uo", "up", "upon", "ups", "ur", "us", "use", "used", "useful", "usefully", "usefulness", "uses", "using", "usually", "ut", "v", "va", "value", "various", "vd", "ve", "ve", "very", "via", "viz", "vj", "vo", "vol", "vols", "volumtype", "vq", "vs", "vt", "vu", "w", "wa", "want", "wants", "was", "wasn", "wasnt", "wasn't", "way", "we", "wed", "we'd", "welcome", "well", "we'll", "well-b", "went", "were", "we're", "weren", "werent", "weren't", "we've", "what", "whatever", "what'll", "whats", "what's", "when", "whence", "whenever", "when's", "where", "whereafter", "whereas", "whereby", "wherein", "wheres", "where's", "whereupon", "wherever", "whether", "which", "while", "whim", "whither", "who", "whod", "whoever", "whole", "who'll", "whom", "whomever", "whos", "who's", "whose", "why", "why's", "wi", "widely", "will", "willing", "wish", "with", "within", "without", "wo", "won", "wonder", "wont", "won't", "words", "world", "would", "wouldn", "wouldnt", "wouldn't", "www", "x", "x1", "x2", "x3", "xf", "xi", "xj", "xk", "xl", "xn", "xo", "xs", "xt", "xv", "xx", "y", "y2", "yes", "yet", "yj", "yl", "you", "youd", "you'd", "you'll", "your", "youre", "you're", "yours", "yourself", "yourselves", "you've", "yr", "ys", "yt", "z", "zero", "zi", "zz"]

    for item in list:
        if item not in stop_words:
            tokens_alpha = non_alpha_split(item)
            #print("filetokensalpha")
            #print(tokens_alpha)
            for token in tokens_alpha:
                #print("file token")
                #print(file_token)
                if token != "":
                    token_lower = token.lower()
                    token_lower = ps.stem(token_lower)
                    #!!!!!
                    #stem and lemmitize here!!!!!!!!!!!!!!!!!!!!!!!
                    #!!!!!

                    #I think we want to add tokens multiple times it probably means it is more meaningful and should be counted multiple times - this is a theory though
                    if token_lower not in tokens:
                        if token_lower not in stop_words:
                            tokens.append(token_lower)

    return tokens


def calculate_score(test_queryset, commit_id):
    from applications.vcs.models import Commit
    from applications.testing.models import Test

    commit = Commit.objects.get(pk=commit_id)

    commit_message = [commit.message]

    defect_closed_by_caused_by_intersection_areas = list(commit.areas.values_list('name', flat=True))
    defect_closed_by_caused_by_intersection_files = list(commit.files.values_list('full_filename', flat=True))
    defect_closed_by_caused_by_intersection_folders = [x.full_filename for x in commit.files.all() if
                                                       not x.is_leaf_node()]
    defect_closed_by_caused_by_intersection_dependent_areas = [x for x in list(
        commit.areas.values_list('dependencies__name', flat=True)) if x]

    result = {}

    test_queryset = test_queryset.distinct('name')

    for test in test_queryset:

        test_names = [test.name]

        test_classes_names = [test.class_name]

        test_areas = [test.area.name]

        test_names_tokens = get_tokens_from_list(test_names)
        test_classes_names_tokens = get_tokens_from_list(test_classes_names)
        test_areas_tokens = get_tokens_from_list(test_areas)

        test_multiple_tokens = common_elements(test_names_tokens, test_classes_names_tokens)
        test_multiple_tokens = common_elements(test_multiple_tokens, test_areas_tokens)

        commits_area_tokens = get_tokens_from_list(defect_closed_by_caused_by_intersection_areas)
        commits_file_tokens = get_tokens_from_list(defect_closed_by_caused_by_intersection_files)
        commits_folder_tokens = get_tokens_from_list(defect_closed_by_caused_by_intersection_folders)
        commits_dependent_tokens  = get_tokens_from_list(defect_closed_by_caused_by_intersection_dependent_areas)

        #unsure about line below
        commit_message_tokens = get_tokens_from_list(commit_message)

        commit_multiple_tokens = common_elements(commits_area_tokens, commits_file_tokens)
        commit_multiple_message_tokens = common_elements(commit_multiple_tokens, commit_message)
        #dependent areas shouldn't be added as they will always be separate

        #New Features

        #remove rework and risk

        test_names_to_commit_areas = number_common_elements(test_names_tokens, commits_area_tokens)
        test_names_to_commit_files = number_common_elements(test_names_tokens, commits_file_tokens)
        test_names_to_commit_folders = number_common_elements(test_names_tokens, commits_folder_tokens)
        test_names_to_commit_dependent_areas = number_common_elements(test_names_tokens, commits_dependent_tokens)
        test_names_to_commit_message = number_common_elements(test_names_tokens, commit_message_tokens)
        test_names_to_commit_multiple = number_common_elements(test_names_tokens, commit_multiple_tokens)
        test_names_to_commit_multiple_message = number_common_elements(test_names_tokens, commit_multiple_message_tokens)

        test_class_to_commit_areas = number_common_elements(test_classes_names_tokens, commits_area_tokens)
        test_class_to_commit_files = number_common_elements(test_classes_names_tokens, commits_file_tokens)
        test_class_to_commit_folders = number_common_elements(test_classes_names_tokens, commits_folder_tokens)
        test_class_to_commit_dependent_areas = number_common_elements(test_classes_names_tokens, commits_dependent_tokens)
        test_class_to_commit_message = number_common_elements(test_classes_names_tokens, commit_message_tokens)
        test_class_to_commit_multiple = number_common_elements(test_classes_names_tokens, commit_multiple_tokens)
        test_class_to_commit_multiple_message = number_common_elements(test_classes_names_tokens, commit_multiple_message_tokens)

        test_areas_to_commit_areas = number_common_elements(test_areas_tokens, commits_area_tokens)
        test_areas_to_commit_files = number_common_elements(test_areas_tokens, commits_file_tokens)
        test_areas_to_commit_folders = number_common_elements(test_areas_tokens, commits_folder_tokens)
        test_areas_to_commit_dependent_areas = number_common_elements(test_areas_tokens, commits_dependent_tokens)
        test_areas_to_commit_message = number_common_elements(test_areas_tokens, commit_message_tokens)
        test_areas_to_commit_multiple = number_common_elements(test_areas_tokens, commit_multiple_tokens)
        test_areas_to_commit_multiple_message = number_common_elements(test_areas_tokens, commit_multiple_message_tokens)

        test_multiple_to_commit_areas = number_common_elements(test_multiple_tokens, commits_area_tokens)
        test_multiple_to_commit_files = number_common_elements(test_multiple_tokens, commits_file_tokens)
        test_multiple_to_commit_folders = number_common_elements(test_multiple_tokens, commits_folder_tokens)
        test_multiple_to_commit_dependent_areas = number_common_elements(test_multiple_tokens, commits_dependent_tokens)
        test_multiple_to_commit_message = number_common_elements(test_multiple_tokens, commit_message_tokens)
        test_multiple_to_commit_multiple = number_common_elements(test_multiple_tokens, commit_multiple_tokens)
        test_multiple_to_commit_multiple_message = number_common_elements(test_multiple_tokens, commit_multiple_message_tokens)

        score = (test_names_to_commit_areas
                 + test_names_to_commit_files
                 + test_names_to_commit_folders
                 + test_names_to_commit_dependent_areas
                 + test_names_to_commit_message
                 + test_class_to_commit_multiple
                 + test_class_to_commit_multiple_message
                 + test_class_to_commit_areas
                 + test_class_to_commit_files
                 + test_class_to_commit_folders
                 + test_class_to_commit_dependent_areas
                 + test_class_to_commit_message
                 + test_class_to_commit_multiple
                 + test_class_to_commit_multiple_message
                 + test_areas_to_commit_areas
                 + test_areas_to_commit_files
                 + test_areas_to_commit_folders
                 + test_areas_to_commit_dependent_areas
                 + test_areas_to_commit_message
                 + test_areas_to_commit_multiple
                 + test_areas_to_commit_multiple_message
                 + test_multiple_to_commit_areas
                 + test_multiple_to_commit_files
                 + test_multiple_to_commit_folders
                 + test_multiple_to_commit_dependent_areas
                 + test_multiple_to_commit_message
                 + test_multiple_to_commit_multiple
                 + test_multiple_to_commit_multiple_message)

        result[test.id] = score

    sorted_tuples = sorted(result.items(), key=lambda item: item[1], reverse=True)
    # for k, v in sorted_tuples:
    #     print(f"{k}\t{v}")
    return {k: v for k, v in sorted_tuples}
