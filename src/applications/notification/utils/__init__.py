# -*- coding: utf-8 -*-

from django.db.models import *
from django.db.models.expressions import *
from django.db.models.functions import *

from .alert import *
from .defect import *
from .monitor import *
from .risk import *
from .test_run import *
from .test_prioritization import *
from .risk_analysis import *


def prepare_queryset(period):
    # type: (str) -> QuerySet
    """

    :param period: Notification PERIOD_*
    :return: queryset: QuerySet
    """
    queryset = (
        Notification.objects.filter(period=period)
        .annotate(
            previous_send_datetime=Case(
                When(
                    schedule_last_send__isnull=False, then=F('schedule_last_send')
                ),
                default=Now(), output_field=DateTimeField()
            ),
            previous_send_date=TruncDate('previous_send_datetime'),
            previous_send_weekday=ExtractWeekDay('previous_send_datetime'),
            previous_send_hour=ExtractHour('previous_send_datetime'),
        )
        .annotate(
            previous_send_tz_datetime=Func('previous_send_datetime', template='%(expressions)s AT TIME ZONE schedule_timezone'),
            previous_send_tz_date=TruncDate(Func('previous_send_datetime', template='%(expressions)s AT TIME ZONE schedule_timezone')),
            previous_send_tz_weekday=ExtractWeekDay(Func('previous_send_datetime', template='%(expressions)s AT TIME ZONE schedule_timezone')),
            previous_send_tz_hour=ExtractHour(Func('previous_send_datetime', template='%(expressions)s AT TIME ZONE schedule_timezone')),
        )
        .annotate(
            current_datetime=Now(),
        )
        .annotate(
            current_tz_datetime=Func('current_datetime', template='%(expressions)s AT TIME ZONE schedule_timezone'),
            current_tz_date=TruncDate(Func('current_datetime', template='%(expressions)s AT TIME ZONE schedule_timezone')),
            current_tz_weekday=ExtractWeekDay(Func('current_datetime', template='%(expressions)s AT TIME ZONE schedule_timezone')),
            current_tz_hour=ExtractHour(Func('current_datetime', template='%(expressions)s AT TIME ZONE schedule_timezone')),
        )
        .annotate(
            next_send_tz_datetime=Case(
                When(
                    period=Notification.PERIOD_IMMEDIATELY, then=F('current_tz_datetime')
                ),
                When(
                    period=Notification.PERIOD_DAILY, then=F('previous_send_tz_datetime') + datetime.timedelta(days=1)
                ),
                When(
                    period=Notification.PERIOD_WEEKLY, then=F('previous_send_tz_datetime') + datetime.timedelta(weeks=1)
                ),
                When(
                    period=Notification.PERIOD_FORTNIGHTLY, then=F('previous_send_tz_datetime') + datetime.timedelta(weeks=2)
                ), output_field=DateTimeField()
            )
        )
        .annotate(
            next_send_tz_date=TruncDate(F('next_send_tz_datetime')),
            next_send_tz_weekday=ExtractWeekDay(F('next_send_tz_datetime')),
            next_send_tz_hour=ExtractHour(F('next_send_tz_datetime')),
        )
        .annotate(
            weekday_delta=Case(
                When(
                    schedule_weekday__isnull=False,
                    then=ExpressionWrapper(F('next_send_tz_weekday') - F('schedule_weekday'),
                                           output_field=IntegerField())
                ),
                default=Value(0), output_field=IntegerField()
            ),
            hour_delta=Case(
                When(
                    Q(schedule_hour__isnull=False) & Q(schedule_hour__gte=0) & Q(schedule_hour__lte=23),
                    then=ExpressionWrapper(F('next_send_tz_hour') - F('schedule_hour'),
                                           output_field=IntegerField())
                ),
                default=Value(0), output_field=IntegerField()
            ),
        )
        .annotate(
            weekday_delta=Func('weekday_delta',
                               template="make_interval(days => %(expressions)s::integer)",
                               output_field=DurationField()),
            hour_delta=Func('hour_delta',
                            template="make_interval(hours => %(expressions)s::integer)",
                            output_field=DurationField()),
        )
        .annotate(
            next_send_tz_datetime=ExpressionWrapper(F('next_send_tz_datetime') -
                                                    F('weekday_delta') -
                                                    F('hour_delta'),
                                                    output_field=DateTimeField())
        )
        .annotate(
            next_send_tz_date=TruncDate(F('next_send_tz_datetime')),
            next_send_tz_weekday=ExtractWeekDay(F('next_send_tz_datetime')),
            next_send_tz_hour=ExtractHour(F('next_send_tz_datetime')),
        )
        .annotate(
            allow_send=Case(
                When(
                    period=Notification.PERIOD_IMMEDIATELY, then=True
                ),
                When(
                    Q(period=Notification.PERIOD_DAILY) &
                    Q(current_tz_date__gte=F('next_send_tz_date')) &
                    Q(current_tz_hour__gte=F('next_send_tz_hour')),
                    then=True
                ),
                When(
                    Q(period=Notification.PERIOD_WEEKLY) &
                    Q(current_tz_date__gte=F('next_send_tz_date')) &
                    Q(current_tz_hour__gte=F('next_send_tz_hour')) &
                    Q(current_tz_weekday=F('next_send_tz_weekday')),
                    then=True
                ),
                When(
                    Q(period=Notification.PERIOD_FORTNIGHTLY) &
                    Q(current_tz_date__gte=F('next_send_tz_date')) &
                    Q(current_tz_hour__gte=F('next_send_tz_hour')) &
                    Q(current_tz_weekday=F('next_send_tz_weekday')),
                    then=True
                ),
                default=False, output_field=BooleanField()
            )
        )
    )
    # dbg = list(queryset)
    queryset = queryset.filter(allow_send=True)
    return queryset


def check_updates_one_off():
    """

    :return:
    """
    try:

        notification_queryset = Notification.objects.filter(
            period=Notification.PERIOD_ONE_OFF).select_related('project')

        for notify in notification_queryset:
            start_datetime = notify.one_off_start_date
            end_datetime = notify.one_off_end_date
            if notify.type == Notification.TYPE_ALERT:
                check_alerts_one_off(notify, date_range=(start_datetime, end_datetime,))
            if notify.type == Notification.TYPE_RISK:
                check_risks_one_off(notify, date_range=(start_datetime, end_datetime,))
            if notify.type == Notification.TYPE_DEFECT:
                check_defects_one_off(notify, date_range=(start_datetime, end_datetime,))
            if notify.type == Notification.TYPE_TEST_RUN:
                check_test_runs_one_off(notify, date_range=(start_datetime, end_datetime,))
            if notify.type == Notification.TYPE_MONITOR:
                check_monitor_one_off(notify, date_range=(start_datetime, end_datetime,))
            if notify.type == Notification.TYPE_TEST_PRIORITIZATION:
                check_test_prioritization_one_off(notify, date_range=(start_datetime, end_datetime,))
            if notify.type == Notification.TYPE_RISK_ANALYSIS:
                check_risks_analysis_one_off(notify, date_range=(start_datetime, end_datetime,))

        notification_queryset.delete()
    except Exception as e:
        print(e)


def check_updates_immediately():
    """

    :return:
    """
    try:

        notification_queryset = list(prepare_queryset(period=Notification.PERIOD_IMMEDIATELY).select_related('project'))

        for notify in notification_queryset:
            if notify.type == Notification.TYPE_RISK:
                check_risks_immediately(notify)
            if notify.type == Notification.TYPE_ALERT:
                check_alerts_immediately(notify)

            if notify.type == Notification.TYPE_DEFECT:
                check_defects_immediately(notify)
            if notify.type == Notification.TYPE_TEST_RUN:
                check_test_runs_immediately(notify)
            if notify.type == Notification.TYPE_MONITOR:
                check_monitor_immediately(notify)
            if notify.type == Notification.TYPE_TEST_PRIORITIZATION:
                check_test_prioritization_immediately(notify)
            if notify.type == Notification.TYPE_RISK_ANALYSIS:
                check_risks_analysis_immediately(notify)

    except Exception as e:
        print(e)


def check_updates_daily():
    """

    :return:
    """
    try:

        notification_queryset = list(prepare_queryset(period=Notification.PERIOD_DAILY).select_related('project'))

        for notify in notification_queryset:
            if notify.type == Notification.TYPE_RISK:
                check_risks_daily(notify)
            if notify.type == Notification.TYPE_ALERT:
                check_alerts_daily(notify)
            if notify.type == Notification.TYPE_DEFECT:
                check_defects_daily(notify)
            if notify.type == Notification.TYPE_TEST_RUN:
                check_test_runs_daily(notify)
            if notify.type == Notification.TYPE_MONITOR:
                check_monitor_daily(notify)
            if notify.type == Notification.TYPE_TEST_PRIORITIZATION:
                check_test_prioritization_daily(notify)
            if notify.type == Notification.TYPE_RISK_ANALYSIS:
                check_risks_analysis_daily(notify)

    except Exception as e:
        print(e)


def check_updates_weekly():
    """

    :return:
    """
    try:

        notification_queryset = list(prepare_queryset(period=Notification.PERIOD_WEEKLY).select_related('project'))

        for notify in notification_queryset:
            if notify.type == Notification.TYPE_RISK:
                check_risks_weekly(notify)
            if notify.type == Notification.TYPE_ALERT:
                check_alerts_weekly(notify)
            if notify.type == Notification.TYPE_DEFECT:
                check_defects_weekly(notify)
            if notify.type == Notification.TYPE_TEST_RUN:
                check_test_runs_weekly(notify)
            if notify.type == Notification.TYPE_MONITOR:
                check_monitor_weekly(notify)
            if notify.type == Notification.TYPE_TEST_PRIORITIZATION:
                check_test_prioritization_weekly(notify)
            if notify.type == Notification.TYPE_RISK_ANALYSIS:
                check_risks_analysis_weekly(notify)

    except Exception as e:
        print(e)


def check_updates_fortnightly():
    """

    :return:
    """
    try:

        notification_queryset = list(prepare_queryset(period=Notification.PERIOD_FORTNIGHTLY).select_related('project'))

        for notify in notification_queryset:
            if notify.type == Notification.TYPE_RISK:
                check_risks_fortnightly(notify)
            if notify.type == Notification.TYPE_ALERT:
                check_alerts_fortnightly(notify)
            if notify.type == Notification.TYPE_DEFECT:
                check_defects_fortnightly(notify)
            if notify.type == Notification.TYPE_TEST_RUN:
                check_test_runs_fortnightly(notify)
            if notify.type == Notification.TYPE_MONITOR:
                check_monitor_fortnightly(notify)
            if notify.type == Notification.TYPE_TEST_PRIORITIZATION:
                check_test_prioritization_fortnightly(notify)
            if notify.type == Notification.TYPE_RISK_ANALYSIS:
                check_risks_analysis_fortnightly(notify)

    except Exception as e:
        print(e)
