# -*- coding: utf-8 -*-
import time
from datetime import timedelta, date

from django.db import models
from django.db.models import Q, F, Count, Value, CharField, Subquery, OuterRef
from django.db.models.functions import Concat, Coalesce
from django.utils import timezone

from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.db.models import Count
from django.db.models.expressions import *
from django.db.models.lookups import GreaterThan
from django.db.models.functions import *

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


TEST_RUNS_ML_USING_THRESHOLD = 500
MINIMAL_NUMBER_OF_TESTRUNS_FOR_ML_MODEL_USING = 50


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
    prioritize_task(commits_sha=commit_queryset_sha)

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
        ml_predictor = MLModel.open_model(test_suite_id=test_suite.id)
    ml_model_existing_flag = ml_predictor is not None

    if ml_model_existing_flag is False or test_run_count < MINIMAL_NUMBER_OF_TESTRUNS_FOR_ML_MODEL_USING:
        use_sql = True

    priority = params["priority"]
    if priority == PRIORITY_HIGH:
        if use_sql:
            queryset = get_default_high_queryset(queryset, commit_list, params=params)
        else:
            if test_run_count >= TEST_RUNS_ML_USING_THRESHOLD:
                queryset = ml_predictor.get_test_prioritization(queryset, commit_queryset, params=params)['h']
                queryset = queryset.distinct('name')
            else:
                ml_prediction_results = ml_predictor.get_test_prioritization(queryset, commit_queryset)
                ml_unassigned_tests_num = ml_prediction_results['u'].count()
                original_unassigned_num = get_default_unassigned_queryset(queryset, params=params).count()
                if original_unassigned_num > ml_unassigned_tests_num:
                    queryset = ml_prediction_results['h'].distinct('name')
                else:
                    queryset = get_default_high_queryset(queryset, commit_list, params=params)

    elif priority == PRIORITY_MEDIUM:
        if use_sql:
            queryset = get_default_medium_queryset(queryset, commit_list, params=params)
        else:
            if test_run_count >= TEST_RUNS_ML_USING_THRESHOLD:
                queryset = ml_predictor.get_test_prioritization(queryset, commit_queryset, params=params)['m']
                queryset = queryset.distinct('name')
            else:
                ml_prediction_results = ml_predictor.get_test_prioritization(queryset, commit_queryset)
                ml_unassigned_tests_num = ml_prediction_results['u'].count()
                original_unassigned_num = get_default_unassigned_queryset(queryset, params=params).count()
                if original_unassigned_num > ml_unassigned_tests_num:
                    queryset = ml_prediction_results['m'].distinct('name')
                else:
                    queryset = get_default_medium_queryset(queryset, commit_list, params=params)

    elif priority == PRIORITY_LOW:
        if use_sql:
            queryset = get_default_low_queryset(queryset, commit_list, params=params)
        else:
            if test_run_count >= TEST_RUNS_ML_USING_THRESHOLD:
                queryset = ml_predictor.get_test_prioritization(queryset, commit_queryset, params=params)['l']
                queryset = queryset.distinct('name')
            else:
                ml_prediction_results = ml_predictor.get_test_prioritization(queryset, commit_queryset)
                ml_unassigned_tests_num = ml_prediction_results['u'].count()
                original_unassigned_num = get_default_unassigned_queryset(queryset, params=params).count()
                if original_unassigned_num > ml_unassigned_tests_num:
                    queryset = ml_prediction_results['l'].distinct('name')
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
                queryset = ml_predictor.get_test_prioritization_top_by_percent(
                    queryset, commit_queryset, params["percent"], params=params)['t']
                queryset = queryset.distinct('name')
            else:
                queryset = get_default_top20_queryset(queryset, commit_list, percent=params["percent"], params=params)

    elif priority == PRIORITY_PERCENT:
        if use_sql:
            queryset = get_default_by_percent_queryset(queryset, commit_list, percent=params["percent"], params=params)
        else:
            if test_run_count >= TEST_RUNS_ML_USING_THRESHOLD:
                queryset = ml_predictor.get_test_prioritization_top_by_percent(
                    queryset, commit_queryset, params["percent"], params=params)['t']
                queryset = queryset.distinct('name')
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

    testsuitename = params.get("classname", False)
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


def get_default_top20_queryset(queryset, commits_ids, percent, params=None):
    qs = queryset

    commit = params["commit"]

    default_queryset = list()

    result = calculate_similar_by_commit(qs, commit.pk, percent=percent)

    test_ids = set(result['tests'])

    # default_queryset.extend(list(get_default_high_queryset(queryset, commits_ids).values_list('id', flat=True)))
    default_queryset.extend(set(list(get_default_medium_queryset(queryset, commits_ids, params=params).values_list('id', flat=True))))
    default_queryset.extend(set(list(get_default_unassigned_queryset(queryset, params=params).values_list('id', flat=True))))

    if len(test_ids) > 0:
        default_queryset.extend(list(test_ids))

    _ids = default_queryset

    _count = qs.count()
    _per = int(percent * _count / 100)
    _ids = default_queryset[:_per]

    qs = Test.objects.filter(id__in=_ids)
    return qs.distinct('name')


def get_default_by_percent_queryset(queryset, commits_ids, percent, params=None):
    qs = queryset

    commit = params["commit"]

    default_queryset = list()

    result = calculate_similar_by_commit(qs, commit.pk, percent=percent)

    test_ids = set(result['tests'])

    # default_queryset.extend(list(get_default_high_queryset(queryset, commits_ids).values_list('id', flat=True)))
    # default_queryset.extend(list(get_default_medium_queryset(queryset, commits_ids).values_list('id', flat=True)))
    # default_queryset.extend(list(get_default_unassigned_queryset(queryset).values_list('id', flat=True)))

    # print("--- BEGIN DEFAULT PERCENT")
    # start_time = time.time()
    # print("--- %s seconds ---" % (time.time() - start_time))
    low_queryset = get_default_low_queryset(queryset, commits_ids, params=params).values_list('id', flat=True)
    # print("--- LOW: %s seconds ---" % (time.time() - start_time))
    default_queryset.extend(set(list(low_queryset)))
    # print("--- Default: %s seconds ---" % (time.time() - start_time))
    if len(test_ids) > 0:
        default_queryset.extend(list(test_ids))

    _count = len(default_queryset)
    _per = int((percent * _count) / 100)
    _ids = default_queryset[:_per]

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
