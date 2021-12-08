# -*- coding: utf-8 -*-
import logging
import pytz
import datetime
from django.db.models import Max
from applications.notification.models import Notification
from applications.notification.utils.email import send_notification_email
from applications.vcs.models import Commit
from django.db.models import Max, Prefetch, OuterRef, Subquery, Count, Case, When, F, Q
from django.db.models.functions import TruncSecond
from django.utils import timezone
from applications.testing.models import TestRun, TestRunResult, Defect, Test
from applications.api.report.views import TestReportModelViewSet

from django.http import HttpRequest
from rest_framework.request import Request


def percentage(part, whole):
    if part == 0 or whole == 0:
        result = '%.2f' % (0.0)
    else:
        result = '%.2f' % (100.0 * part / whole)
    return result + '%'


def get_statistic_for_related_defects(test_ids_by_priority):
    all_high_tests = test_ids_by_priority['high']
    all_medium_tests = test_ids_by_priority['medium']
    all_low_tests = test_ids_by_priority['low']
    all_unassigned_tests = test_ids_by_priority['unassigned']

    high_defects_queryset = Defect.objects.filter(type=Defect.TYPE_PROJECT,
                                                  associated_tests__id__in=all_high_tests).distinct('id')
    high_defects_number = high_defects_queryset.count()

    excluded_defects_ids = list(high_defects_queryset.values_list('id', flat=True)[:])
    medium_defects_queryset = Defect.objects.filter(type=Defect.TYPE_PROJECT,
                                                    associated_tests__id__in=all_medium_tests)
    medium_defects_queryset = medium_defects_queryset.exclude(id__in=excluded_defects_ids).distinct('id')
    medium_defects_number = medium_defects_queryset.count()

    excluded_defects_ids += list(medium_defects_queryset.values_list('id', flat=True))
    low_defects_queryset = Defect.objects.filter(type=Defect.TYPE_PROJECT,
                                                 associated_tests__in=all_low_tests)
    low_defects_queryset = low_defects_queryset.exclude(id__in=excluded_defects_ids).distinct('id')
    low_defects_number = low_defects_queryset.count()

    excluded_defects_ids += list(low_defects_queryset.values_list('id', flat=True))
    unassigned_defects_queryset = Defect.objects.filter(type=Defect.TYPE_PROJECT,
                                                        associated_tests__in=all_unassigned_tests)
    unassigned_defects_queryset = unassigned_defects_queryset.exclude(id__in=excluded_defects_ids).distinct('id')
    unassigned_defects_number = unassigned_defects_queryset.count()

    total_number_of_defects = high_defects_number
    total_number_of_defects += medium_defects_number
    total_number_of_defects += low_defects_number
    total_number_of_defects += unassigned_defects_number

    result = {
        'number_low_defects': low_defects_number,

        'percentage_high_defects': percentage(high_defects_number, total_number_of_defects),
        'percentage_medium_defects': percentage(medium_defects_number, total_number_of_defects),
        'percentage_low_defects': percentage(low_defects_number, total_number_of_defects),
        'percentage_unassigned_defects': percentage(unassigned_defects_number, total_number_of_defects),
    }
    return result


def calculate_tests_number_statistic(tests_number_by_priority):
    all_high_tests_number = tests_number_by_priority['high']
    all_medium_tests_number = tests_number_by_priority['medium']
    all_low_tests_number = tests_number_by_priority['low']
    all_unassigned_tests_number = tests_number_by_priority['unassigned']

    total_number_of_tests = all_high_tests_number
    total_number_of_tests += all_medium_tests_number
    total_number_of_tests += all_low_tests_number
    total_number_of_tests += all_unassigned_tests_number
    total_tests_info = {
        'number_high_tests': all_high_tests_number,
        'number_medium_tests': all_medium_tests_number,
        'number_low_tests': all_low_tests_number,
        'number_unassigned_tests': all_unassigned_tests_number,

        'percentage_high_tests': percentage(all_high_tests_number, total_number_of_tests),
        'percentage_medium_tests': percentage(all_medium_tests_number, total_number_of_tests),
        'percentage_low_tests': percentage(all_low_tests_number, total_number_of_tests),
        'percentage_unassigned_tests': percentage(all_unassigned_tests_number, total_number_of_tests),
    }
    return total_tests_info


# TODO: need some refactoring
def calculate_statistic(notify, date_range=None):
    # type: (Notification, tuple) -> dict
    """
        Check updates for notification
    :param notify: Notification instance
    :param date_range: Tuple with datetime objects for one_off range
    :return: result: Dict with results
    """

    all_high_tests = set()
    all_medium_tests = set()
    all_low_tests = set()
    all_unassigned_tests = set()

    all_runned_high_tests = set()
    all_runned_medium_tests = set()
    all_runned_low_tests = set()
    all_runned_unassigned_tests = set()

    all_high_tests_number = 0
    all_medium_tests_number = 0
    all_low_tests_number = 0
    all_unassigned_tests_number = 0

    all_runned_high_tests_number = 0
    all_runned_medium_tests_number = 0
    all_runned_low_tests_number = 0
    all_runned_unassigned_tests_number = 0

    project_commits = Commit.objects.filter(project=notify.project)
    if not date_range:
        previous_send_datetime = notify.previous_send_datetime.replace(tzinfo=pytz.timezone('UTC'))
        project_commits = project_commits.filter(created__gt=previous_send_datetime).order_by('-created')
    else:
        project_commits = project_commits.filter(created__date__range=date_range).order_by('-created')

    queryset = Test.objects.filter(project=notify.project)
    for commit in project_commits:
        request = HttpRequest()
        request.GET['commit'] = str(commit.id)
        request.GET['project'] = str(notify.project.id)
        request.META['HTTP_HOST'] = str(notify.project.organization.site.domain)
        request = Request(request)
        test_view = TestReportModelViewSet(request=request)

        testruns_with_results_on_this_commit = TestRun.objects.filter(commit=commit,
                                                                      test_run_results__isnull=False)
        runned_tests_ids = set(
            Test.objects.filter(test_runs__in=testruns_with_results_on_this_commit).values_list('id', flat=True))

        cur_high_tests = set(test_view.get_high_queryset(queryset.all()).values_list('id', flat=True))
        all_high_tests_number += len(cur_high_tests)
        all_high_tests = all_high_tests.union(cur_high_tests)

        runned_high_tests = cur_high_tests.intersection(runned_tests_ids)
        all_runned_high_tests_number += len(runned_high_tests)
        all_runned_high_tests = all_runned_high_tests.union(runned_high_tests)

        cur_medium_tests = set(test_view.get_medium_queryset(queryset.all()).values_list('id', flat=True))
        all_medium_tests_number += len(cur_medium_tests)
        all_medium_tests = all_medium_tests.union(cur_medium_tests)

        runned_medium_tests = cur_medium_tests.intersection(runned_tests_ids)
        all_runned_medium_tests_number += len(runned_medium_tests)
        all_runned_medium_tests = all_runned_medium_tests.union(runned_high_tests)

        cur_low_tests = set(test_view.get_low_queryset(queryset.all()).values_list('id', flat=True))
        all_low_tests_number += len(cur_low_tests)
        all_low_tests = all_low_tests.union(cur_low_tests)
        runned_low_tests = cur_low_tests.intersection(runned_tests_ids)
        all_runned_low_tests_number += len(runned_low_tests)
        all_runned_low_tests = all_runned_low_tests.union(runned_low_tests)

        cur_unassigned_tests = set(test_view.get_unassigned_queryset(queryset.all()).values_list('id', flat=True))
        all_unassigned_tests_number += len(cur_unassigned_tests)
        all_unassigned_tests = all_unassigned_tests.union(cur_unassigned_tests)
        runned_unassigned_tests = cur_medium_tests.intersection(runned_tests_ids)
        all_runned_unassigned_tests_number += len(runned_unassigned_tests)
        all_runned_unassigned_tests = all_runned_unassigned_tests.union(runned_unassigned_tests)

    tests_numbers_by_priority = {
        'high': all_high_tests_number,
        'medium': all_medium_tests_number,
        'low': all_low_tests_number,
        'unassigned': all_unassigned_tests_number
    }
    tests_by_priority = {
        'high': all_high_tests,
        'medium': all_medium_tests,
        'low': all_low_tests,
        'unassigned': all_unassigned_tests
    }
    total_tests_info = calculate_tests_number_statistic(tests_numbers_by_priority)
    defects_for_all_tests_info = get_statistic_for_related_defects(tests_by_priority)
    total_tests_info.update(defects_for_all_tests_info)

    runned_tests_by_priority = {
        'high': all_runned_high_tests,
        'medium': all_runned_medium_tests,
        'low': all_runned_low_tests,
        'unassigned': all_runned_unassigned_tests
    }
    runned_tests_numbers_by_priority = {
        'high': all_runned_high_tests_number,
        'medium': all_runned_medium_tests_number,
        'low': all_runned_low_tests_number,
        'unassigned': all_runned_unassigned_tests_number

    }
    total_runned_tests_info = calculate_tests_number_statistic(runned_tests_numbers_by_priority)
    defects_for_runned_tests_info = get_statistic_for_related_defects(runned_tests_by_priority)
    total_runned_tests_info.update(defects_for_runned_tests_info)

    result = {
        'total_tests_info': total_tests_info,
        'runned_tests_info': total_runned_tests_info
    }
    return result


def check_updates(notify, date_range=None):
    # type: (Notification, tuple) -> None
    """
        Check updates for notification
    :param notify: Notification instance
    :param date_range: Tuple with datetime objects for one_off range
    :return:
    """

    try:

        if notify.period in [Notification.PERIOD_IMMEDIATELY, Notification.PERIOD_DAILY]:
            raise RuntimeError('This function not allowed for notification with this period.')

        email_context = calculate_statistic(notify, date_range)
        email_context['project_name'] = notify.project.name
        email_context['period'] = notify.get_period_display()
        emails = notify.emails.split(',')
        for email in emails:
            email_context['email'] = email
            send_notification_email(notify=notify, context=email_context)

        if not notify.period == Notification.PERIOD_ONE_OFF:
            schedule_last_send = notify.current_datetime.replace(tzinfo=pytz.timezone('UTC'))
            notify.schedule_last_send = schedule_last_send
            notify.save()

    except Exception as e:
        print(e)


def check_test_prioritization_one_off(notify, date_range):
    # type: (Notification, tuple) -> None
    """
        Check updates for test_prioritization notification with one off period
    :param notify: Notification instance
    :param date_range: Tuple with datetime objects
    :return:
    """
    check_updates(notify, date_range)


def check_test_prioritization_immediately(notify):
    raise NotImplementedError('This type not allowed for "Test Priority" notification')


def check_test_prioritization_daily(notify):
    raise NotImplementedError('This type not allowed for "Test Priority" notification')


def check_test_prioritization_weekly(notify):
    # type: (Notification) -> None
    """
        Check updates for test_prioritization notification with weekly period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_test_prioritization_fortnightly(notify):
    # type: (Notification) -> None
    """
        Check updates for test_prioritization notification with fortnightly period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)
