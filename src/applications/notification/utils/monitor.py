# -*- coding: utf-8 -*-
import datetime

import pytz
from django.db import models
from django.db.models import Func

from applications.notification.models import Notification
from applications.notification.utils.email import send_notification_email
from applications.vcs.models import Commit, Area, File


def check_updates(notify, date_range=None):
    # type: (Notification, tuple) -> None
    """
        Check updates for notification
    :param notify: Notification instance
    :param date_range: Tuple with datetime objects for one_off range
    :return:
    """

    try:
        monitor_areas = notify.extra_params.get('monitor_areas')
        monitor_files = notify.extra_params.get('monitor_files')
        areas_prefetch = models.Prefetch('areas', queryset=Area.objects.exclude(name='Default Area'))

        commit_queryset = Commit.objects.filter(project=notify.project)

        if not date_range:
            previous_send_datetime = notify.previous_send_datetime.replace(tzinfo=pytz.timezone('UTC'))
            commit_queryset = commit_queryset.filter(created__gt=previous_send_datetime)
        else:
            commit_queryset = commit_queryset.filter(created__date__range=date_range)

        commit_queryset = commit_queryset.filter(
            models.Q(areas__in=monitor_areas) | models.Q(files__in=monitor_files)
        ).prefetch_related('files', areas_prefetch).distinct()

        areas_queryset = Area.objects.filter(pk__in=monitor_areas)
        files_queryset = File.objects.filter(pk__in=monitor_files)

        email_context = {}
        if commit_queryset.count() > 0:
            emails = notify.emails.split(',')

            email_context['period'] = notify.get_period_display()
            email_context['user_timezone'] = notify.schedule_timezone
            email_context['commits'] = list(commit_queryset)
            email_context['areas'] = list(areas_queryset)
            email_context['files'] = list(files_queryset)

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


def check_monitor_one_off(notify, date_range):
    # type: (Notification, tuple) -> None
    """
        Check updates for monitor notification with one off period
    :param notify: Notification instance
    :param date_range: Tuple with datetime objects
    :return:
    """
    check_updates(notify, date_range)


def check_monitor_immediately(notify):
    # type: (Notification) -> None
    """
        Check updates for monitor notification with immediately period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_monitor_daily(notify):
    # type: (Notification) -> None
    """
        Check updates for monitor notification with daily period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_monitor_weekly(notify):
    # type: (Notification) -> None
    """
        Check updates for monitor notification with weekly period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_monitor_fortnightly(notify):
    # type: (Notification) -> None
    """
        Check updates for monitor notification with fortnightly period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)
