# -*- coding: utf-8 -*-
import datetime

import pytz
from django.db import models
from django.db.models import Max, Func

from applications.notification.models import Notification
from applications.notification.utils.email import send_notification_email
from applications.vcs.models import Commit, Area


def check_updates(notify, date_range=None):
    # type: (Notification, tuple) -> None
    """
        Check updates for notification
    :param notify: Notification instance
    :param date_range: Tuple with datetime objects for one_off range
    :return:
    """

    try:
        commit_queryset = Commit.objects.filter(project=notify.project)
        areas_prefetch = models.Prefetch('areas', queryset=Area.objects.exclude(name='Default Area'))

        if not date_range:
            previous_send_datetime = notify.previous_send_datetime.replace(tzinfo=pytz.timezone('UTC'))
            commit_queryset = commit_queryset.filter(updated__gt=previous_send_datetime)
        else:
            commit_queryset = commit_queryset.filter(updated__date__range=date_range)

        commit_queryset = list(commit_queryset.filter(
            riskiness__gt=float(0.25)
            ).select_related('project').prefetch_related(areas_prefetch).annotate(
                max_time=Max('updated'))[:20]
        )

        email_context = {}
        if len(commit_queryset) > 0:

            emails = notify.emails.split(',')

            email_context['period'] = notify.get_period_display()
            email_context['commits'] = commit_queryset
            email_context['user_timezone'] = notify.schedule_timezone

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


def check_risks_one_off(notify, date_range):
    # type: (Notification, tuple) -> None
    """
        Check updates for risks notification with one off period
    :param notify: Notification instance
    :param date_range: Tuple with datetime objects
    :return:
    """
    check_updates(notify, date_range)


def check_risks_immediately(notify):
    # type: (Notification) -> None
    """
        Check updates for risks notification with daily period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_risks_daily(notify):
    # type: (Notification) -> None
    """
        Check updates for risks notification with daily period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_risks_weekly(notify):
    # type: (Notification) -> None
    """
        Check updates for risks notification with daily period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_risks_fortnightly(notify):
    # type: (Notification) -> None
    """
        Check updates for risks notification with daily period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)
