# -*- coding: utf-8 -*-
import datetime

import pytz
from django.db.models import Max

from applications.notification.models import Notification
from applications.notification.utils.email import send_notification_email
from applications.testing.models import Defect


def check_updates(notify, date_range=None):
    # type: (Notification, tuple) -> None
    """
        Check updates for notification
    :param notify: Notification instance
    :param date_range: Tuple with datetime objects for one_off range
    :return:
    """

    try:
        defect_queryset = Defect.objects.filter(project=notify.project)
        if not date_range:
            previous_send_datetime = notify.previous_send_datetime.replace(tzinfo=pytz.timezone('UTC'))
            defect_queryset = defect_queryset.filter(updated__gt=previous_send_datetime)
        else:
            defect_queryset = defect_queryset.filter(updated__date__range=date_range)

        defect_queryset = list(defect_queryset.select_related(
            'project', 'created_by_test').annotate(max_time=Max('updated'))[:10])

        email_context = {}

        if len(defect_queryset) > 0:
            emails = notify.emails.split(',')

            email_context['period'] = notify.get_period_display()
            email_context['defects'] = defect_queryset

            for email in emails:
                email_context['user_timezone'] = notify.schedule_timezone
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


def check_defects_one_off(notify, date_range):
    # type: (Notification, tuple) -> None
    """
        Check updates for defects notification with one off period
    :param notify: Notification instance
    :param date_range: Tuple with datetime objects
    :return:
    """
    check_updates(notify, date_range)


def check_defects_immediately(notify):
    # type: (Notification) -> None
    """
        Check updates for defects notification with immediately period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_defects_daily(notify):
    # type: (Notification) -> None
    """
        Check updates for defects notification with daily period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_defects_weekly(notify):
    # type: (Notification) -> None
    """
        Check updates for defects notification with weekly period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_defects_fortnightly(notify):
    # type: (Notification) -> None
    """
        Check updates for defects notification with fortnightly period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)
