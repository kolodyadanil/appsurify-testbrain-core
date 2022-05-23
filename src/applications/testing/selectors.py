# -*- coding: utf-8 -*-
import time
from django.db import models
from django.db.models import Q, F, Count, Value, CharField, Subquery, OuterRef
from django.db.models.functions import Concat, Coalesce
from django.utils import timezone
from applications.testing.models import Test, TestRun, TestSuite, TestRunResult, Defect
from applications.vcs.models import Commit, Area, Branch
from applications.vcs.utils.analysis import calculate_user_analysis, calculate_user_analysis_by_range, \
    avg_per_range, calculate_similar_by_commit
from applications.ml.models import MLModel


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
    qs = queryset
    area_query_set = qs.filter(Q(associated_areas__isnull=False))
    commits_areas = list(Commit.objects.filter(id__in=commits_ids).values_list('areas', flat=True))
    depended_areas_annotations = {
        'depended_area_lvl%d' % i: F('associated_areas'+(LOOKUP_SEP+'dependencies')*i) for i in range(1, 6)}
    area_query_set = area_query_set.annotate(**depended_areas_annotations)
    area_query_filter = Q(associated_areas__in=commits_areas)
    for depended_area_level in depended_areas_annotations.keys():
        area_query_filter |= Q(**{LOOKUP_SEP.join([depended_area_level, 'in']): commits_areas})
    area_query_set = area_query_set.filter(area_query_filter)

    qs = qs.filter(project__commits__id__in=commits_ids)
    qs = qs.filter(
        associated_defects__type=Defect.TYPE_PROJECT,
        associated_defects__status=Defect.STATUS_CLOSED,
        associated_defects__close_type__in=[Defect.CLOSE_TYPE_FIXED, Defect.CLOSE_TYPE_WONT_FIX],
    )

    default_area_id = Area.get_default(project=params['project']).id
    qs = qs.annotate(
        commit__areas=F('project__commits__areas'),
        caused_by_commits__areas=F('associated_defects__caused_by_commits__areas')
    ).filter(
        ~Q(commit__areas=default_area_id) &
        Q(Q(commit__areas=F('caused_by_commits__areas')) | Q(commit__areas=F('area')))
    )
    medium_query = Q(id__in=area_query_set.values_list('id', flat=True))
    medium_query |= Q(id__in=qs.values_list('id', flat=True))

    high_queryset = get_default_high_queryset(queryset, commits_ids, params=params)
    exclude_test_ids = set(list(high_queryset.values_list('id', flat=True)))
    qs = Test.objects.exclude(id__in=exclude_test_ids).filter(medium_query)
    qs = qs.distinct('name')
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


def test_run_report_list(*, params=None):
    """
    'project', 'test_suite', 'test_run_type', 'status', 'is_local'

    params = {
        'organization': Organization(),
        'project': Project(),
        'test_suite': TestSuite() | None,
        'test_run_type': 1 | 2 | 3 | None,
        'status': 1 | 2 | 3 | None,
        'is_local': True | False,
        'ordering': '-start_date' | None
    }

    """
    params = params or {}

    sql_template = """
SELECT "testing_testrunresult"."project_id",
   "testing_testrunresult"."project_name",
   "testing_testrunresult"."test_suite_id",
   "testing_testrunresult"."test_suite_name",
   DATE_TRUNC('second', "testing_testrunresult"."test_run_start_date" AT TIME ZONE 'UTC') AS "start_date",
   COUNT(DISTINCT CASE
                      WHEN "testing_testrunresult"."test_run_id" = "testing_testrunresult"."test_run_id" THEN "testing_testrunresult"."test_id"
                      ELSE NULL
                  END) AS "tests__count",
   COUNT(DISTINCT CASE
                      WHEN "testing_testrunresult"."test_run_id" = "testing_testrunresult"."test_run_id" THEN "testing_defect"."id"
                      ELSE NULL
                  END) AS "created_defects__count",
   COUNT(DISTINCT CASE
                      WHEN (T8."type" IN (2, 4, 1)
                            AND "testing_testrunresult"."test_run_id" = "testing_testrunresult"."test_run_id") THEN "testing_defect_found_test_run_results"."defect_id"
                      ELSE NULL
                  END) AS "founded_defects__flaky_failure__count",
   COUNT(DISTINCT CASE
                      WHEN
                             (SELECT U0."status"
                              FROM "testing_testrunresult" U0
                              INNER JOIN "project_project" U1 ON (U0."project_id" = U1."id")
                              WHERE (U1."organization_id" = %(organization_id)s
                                     AND U0."project_id" = %(project_id)s
                                     AND NOT U0."test_run_is_local"
                                     AND U0."test_id" = "testing_testrunresult"."test_id"
                                     AND U0."test_run_id" = "testing_testrunresult"."test_run_id")
                              ORDER BY DATE_TRUNC('second', U0."test_run_start_date" AT TIME ZONE 'UTC') DESC
                              LIMIT 1) = 'pass' THEN "testing_testrunresult"."test_id"
                      ELSE NULL
                  END) AS "passed_tests__count",
   COUNT(DISTINCT CASE
                      WHEN
                             (SELECT U0."status"
                              FROM "testing_testrunresult" U0
                              INNER JOIN "project_project" U1 ON (U0."project_id" = U1."id")
                              WHERE (U1."organization_id" = %(organization_id)s
                                     AND U0."project_id" = %(project_id)s
                                     AND NOT U0."test_run_is_local"
                                     AND U0."test_id" = "testing_testrunresult"."test_id"
                                     AND U0."test_run_id" = "testing_testrunresult"."test_run_id")
                              ORDER BY DATE_TRUNC('second', U0."test_run_start_date" AT TIME ZONE 'UTC') DESC
                              LIMIT 1) = 'skipped' THEN "testing_testrunresult"."test_id"
                      ELSE NULL
                  END) AS "skipped_tests__count",
   COUNT(DISTINCT CASE
                      WHEN
                             (SELECT U0."status"
                              FROM "testing_testrunresult" U0
                              INNER JOIN "project_project" U1 ON (U0."project_id" = U1."id")
                              WHERE (U1."organization_id" = %(organization_id)s
                                     AND U0."project_id" = %(project_id)s
                                     AND NOT U0."test_run_is_local"
                                     AND U0."test_id" = "testing_testrunresult"."test_id"
                                     AND U0."test_run_id" = "testing_testrunresult"."test_run_id")
                              ORDER BY DATE_TRUNC('second', U0."test_run_start_date" AT TIME ZONE 'UTC') DESC
                              LIMIT 1) = 'fail' THEN "testing_testrunresult"."test_id"
                      ELSE NULL
                  END) AS "failed_tests__count",
   COUNT(DISTINCT CASE
                      WHEN
                             (SELECT U0."status"
                              FROM "testing_testrunresult" U0
                              INNER JOIN "project_project" U1 ON (U0."project_id" = U1."id")
                              WHERE (U1."organization_id" = %(organization_id)s
                                     AND U0."project_id" = %(project_id)s
                                     AND NOT U0."test_run_is_local"
                                     AND U0."test_id" = "testing_testrunresult"."test_id"
                                     AND U0."test_run_id" = "testing_testrunresult"."test_run_id")
                              ORDER BY DATE_TRUNC('second', U0."test_run_start_date" AT TIME ZONE 'UTC') DESC
                              LIMIT 1) = 'broken' THEN "testing_testrunresult"."test_id"
                      ELSE NULL
                  END) AS "broken_tests__count",
   COUNT(DISTINCT CASE
                      WHEN
                             (SELECT U0."status"
                              FROM "testing_testrunresult" U0
                              INNER JOIN "project_project" U1 ON (U0."project_id" = U1."id")
                              WHERE (U1."organization_id" = %(organization_id)s
                                     AND U0."project_id" = %(project_id)s
                                     AND NOT U0."test_run_is_local"
                                     AND U0."test_id" = "testing_testrunresult"."test_id"
                                     AND U0."test_run_id" = "testing_testrunresult"."test_run_id")
                              ORDER BY DATE_TRUNC('second', U0."test_run_start_date" AT TIME ZONE 'UTC') DESC
                              LIMIT 1) IN ('pending', 'skipped', 'not_run') THEN "testing_testrunresult"."test_id"
                      ELSE NULL
                  END) AS "not_run_tests__count",
   SUM("testing_testrunresult"."execution_time") AS "execution_time",
         (SELECT COALESCE(SUM("execution_time"), 0) FROM "testing_testrunresult" WHERE "test_run_id" = "testing_testrun"."previous_test_run_id") AS "previous_execution_time",
   "testing_testrunresult"."test_run_id" AS "id",
   "testing_testrunresult"."test_run_name" AS "name",
   CASE
       WHEN NOT ("testing_testrunresult"."test_run_end_date" IS NULL) THEN DATE_TRUNC('second', "testing_testrunresult"."test_run_end_date" AT TIME ZONE 'UTC')
       ELSE NULL
   END AS "end_date"
FROM "testing_testrunresult"
INNER JOIN "project_project" ON ("testing_testrunresult"."project_id" = "project_project"."id")
INNER JOIN "testing_testrun" ON ("testing_testrunresult"."test_run_id" = "testing_testrun"."id")
LEFT OUTER JOIN "testing_defect" ON ("testing_testrunresult"."id" = "testing_defect"."created_by_test_run_result_id")
LEFT OUTER JOIN "testing_defect_found_test_run_results" ON ("testing_testrunresult"."id" = "testing_defect_found_test_run_results"."testrunresult_id")
LEFT OUTER JOIN "testing_defect" T8 ON ("testing_defect_found_test_run_results"."defect_id" = T8."id")
WHERE ("project_project"."organization_id" = %(organization_id)s
       AND "testing_testrunresult"."project_id" = %(project_id)s
       AND NOT "testing_testrunresult"."test_run_is_local")
GROUP BY "testing_testrunresult"."test_run_id",
         DATE_TRUNC('second', "testing_testrunresult"."test_run_start_date" AT TIME ZONE 'UTC'),
         "testing_testrunresult"."test_run_name",
         "testing_testrunresult"."test_run_type",
         CASE
             WHEN NOT ("testing_testrunresult"."test_run_end_date" IS NULL) THEN DATE_TRUNC('second', "testing_testrunresult"."test_run_end_date" AT TIME ZONE 'UTC')
             ELSE NULL
         END,
         "testing_testrunresult"."project_id",
         "testing_testrunresult"."project_name",
         "testing_testrunresult"."test_suite_id",
         "testing_testrunresult"."test_suite_name",
         "testing_testrun"."previous_test_run_id"
    """

    queryset = TestRunResult.objects.raw(sql_template, params={'organization_id': 73, 'project_id': 469})
    print(queryset.query)
    return queryset
