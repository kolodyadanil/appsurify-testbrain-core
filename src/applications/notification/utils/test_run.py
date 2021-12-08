# -*- coding: utf-8 -*-
import datetime

import pytz
from django.db.models import Max, OuterRef, Subquery, Count, Case, When, F, Q
from django.db.models.functions import TruncSecond

from applications.notification.models import Notification
from applications.notification.utils.email import send_notification_email
from applications.testing.models import TestRunResult, Defect


def check_updates(notify, date_range=None):
    # type: (Notification, tuple) -> None
    """
        Check updates for notification
    :param notify: Notification instance
    :param date_range: Tuple with datetime objects for one_off range
    :return:
    """

    try:
        queryset = TestRunResult.objects.filter(project=notify.project)

        if not date_range:
            previous_send_datetime = notify.previous_send_datetime.replace(tzinfo=pytz.timezone('UTC'))
            queryset = queryset.filter(test_run_updated__gt=previous_send_datetime)
        else:
            queryset = queryset.filter(test_run_updated__date__range=date_range)

        sub_queryset = (
            queryset
                .filter(test_id=OuterRef('test_id'), test_run_id=OuterRef('test_run_id'))
                .values('status')[:1]
        )

        qs = queryset.annotate(
            last_test_run_result=Subquery(sub_queryset)
        ).values(
            'test_run_id'
        ).annotate(
            tests__count=Count(
                Case(
                    When(test_run_id=F('test_run_id'), then=F('test_id')),
                ), distinct=True
            ),
            created_defects__count=Count(
                Case(
                    When(test_run_id=F('test_run_id'), then=F('created_defects__id'))
                ), distinct=True
            ),
            reopened_defects__count=Count(
                Case(
                    When(test_run_id=F('test_run_id'), then=F('reopened_defects__id'))
                ), distinct=True
            ),
            founded_defects__flaky_failure__count=Count(
                Case(
                    When(
                        Q(
                            test_run_id=F('test_run_id'),
                            founded_defects__type__in=[Defect.TYPE_FLAKY, Defect.TYPE_INVALID_TEST,
                                                       Defect.TYPE_ENVIRONMENTAL]
                        ), then=F('founded_defects__id')
                    )
                ), distinct=True
            ),
            passed_tests__count=Count(
                Case(
                    When(
                        Q(
                            # test_run_id=models.F('test_run_id'),
                            last_test_run_result=TestRunResult.STATUS_PASS
                        ), then=F('test_id')
                    )
                ), distinct=True
            ),
            failed_tests__count=Count(
                Case(
                    When(
                        Q(
                            # test_run_id=models.F('test_run_id'),
                            last_test_run_result=TestRunResult.STATUS_FAIL
                        ), then=F('test_id')
                    )
                ), distinct=True
            ),
            broken_tests__count=Count(
                Case(
                    When(
                        Q(
                            # test_run_id=models.F('test_run_id'),
                            last_test_run_result=TestRunResult.STATUS_BROKEN
                        ), then=F('test_id')
                    )
                ), distinct=True
            ),
            not_run_tests__count=Count(
                Case(
                    When(
                        Q(
                            # test_run_id=models.F('test_run_id'),
                            last_test_run_result__in=[TestRunResult.STATUS_PENDING, TestRunResult.STATUS_SKIPPED,
                                                      TestRunResult.STATUS_NOT_RUN]
                        ), then=F('test_id')
                    )
                ), distinct=True
            ),
            id=F('test_run_id'),
            name=F('test_run_name'),
            type=F('test_run_type'),
            start_date=TruncSecond(F('test_run_start_date')),
            end_date=Case(
                When(
                    ~Q(test_run_end_date=None),
                    then=TruncSecond(F('test_run_end_date'))
                )
            ),
        ).annotate(max_time=Max('test_run_updated')).values(
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
            'reopened_defects__count',
            'founded_defects__flaky_failure__count',

            'passed_tests__count',
            'failed_tests__count',
            'broken_tests__count',
            'not_run_tests__count',
            'max_time',
            'created',
        )

        test_run_queryset = list(qs[:10])

        email_context = {}

        if len(test_run_queryset) > 0:
            from .build_url import build_absolute_uri
            emails = notify.emails.split(',')

            email_context['user_timezone'] = notify.schedule_timezone
            email_context['period'] = notify.get_period_display()
            email_context['test_runs'] = test_run_queryset
            email_context['test_run_url'] = build_absolute_uri(notify.project.organization, '/test-runs/')

            for email in emails:
                email_context['email'] = email
                send_notification_email(notify=notify, context=email_context)

        if not notify.period == Notification.PERIOD_ONE_OFF:
            if notify.period == Notification.PERIOD_IMMEDIATELY:
                schedule_last_send = datetime.datetime.now().replace(tzinfo=pytz.timezone('UTC'))
            else:
                schedule_last_send = notify.current_datetime.replace(tzinfo=pytz.timezone('UTC'))

            notify.schedule_last_send = schedule_last_send
            notify.save()

    except Exception as e:
        print(e)


def check_test_runs_one_off(notify, date_range):
    # type: (Notification, tuple) -> None
    """
        Check updates for test runs notification with one off period
    :param notify: Notification instance
    :param date_range: Tuple with datetime objects
    :return:
    """
    check_updates(notify, date_range)


def check_test_runs_immediately(notify):
    # type: (Notification) -> None
    """
        Check updates for test runs notification with immediately period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_test_runs_daily(notify):
    # type: (Notification) -> None
    """
        Check updates for test runs notification with immediately period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_test_runs_weekly(notify):
    # type: (Notification) -> None
    """
        Check updates for test runs notification with immediately period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_test_runs_fortnightly(notify):
    # type: (Notification) -> None
    """
        Check updates for test runs notification with immediately period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)
