# -*- coding: utf-8 -*-
import datetime

import dateutil.parser
import pytz
from django.contrib.postgres.fields.jsonb import KeyTransform
from django.db import models
from django.db.models.expressions import Func

from applications.notification.models import Notification
from applications.notification.utils.email import send_notification_email
from applications.vcs.models import Commit, Area, File


def areas_changed_notification(notify, commit_queryset):
    # type: (Notification, QuerySet) -> QuerySet
    """

    :param notify: Notification instance
    :param commit_queryset: QuerySet with Commit objects
    :return: commit_queryset: QuerySet with Commit objects
    """

    value_changed = notify.extra_params.get('alert_areas').get('value')
    commit_queryset = commit_queryset.annotate(areas_count=models.Sum(
        models.Case(
            models.When(areas__name='Default Area', then=0),
            default=1, output_field=models.IntegerField()))
    ).filter(areas_count__gt=value_changed)

    return commit_queryset


def commits_has_not_change(notify, commit_queryset):
    # type: (Notification, QuerySet) -> QuerySet
    """

    :param notify: Notification instance
    :param commit_queryset: QuerySet with Commit objects
    :return: commit_queryset: QuerySet with Commit objects
    """

    commit_queryset = Commit.objects.none()

    return commit_queryset


def commit_lines_changed(notify, commit_queryset):
    # type: (Notification, QuerySet) -> QuerySet
    """

    :param notify: Notification instance
    :param commit_queryset: QuerySet with Commit objects
    :return: commit_queryset: QuerySet with Commit objects
    """

    value_changed = notify.extra_params.get('alert_lines').get('value')

    commit_queryset = commit_queryset.annotate(total_lines=KeyTransform('total', 'stats')).filter(
        total_lines__gt=value_changed)

    return commit_queryset


def commit_files_changed(notify, commit_queryset):
    # type: (Notification, QuerySet) -> QuerySet
    """

    :param notify: Notification instance
    :param commit_queryset: QuerySet with Commit objects
    :return: commit_queryset: QuerySet with Commit objects
    """

    value_changed = notify.extra_params.get('alert_files').get('value')

    commit_queryset = commit_queryset.annotate(filechange_count=models.Count('filechange')).filter(
        filechange_count__gt=value_changed)

    return commit_queryset


def commit_authors_changed(notify, commit_queryset):
    # type: (Notification, QuerySet) -> QuerySet
    """

    :param notify: Notification instance
    :param commit_queryset: QuerySet with Commit objects
    :return: commit_queryset: QuerySet with Commit objects
    """

    value_changed = notify.extra_params.get('alert_authors').get('value')

    commit_queryset = commit_queryset.annotate(commit_author=KeyTransform('name', 'author')).filter(
        commit_author=value_changed)

    return commit_queryset


def commit_time_frame(notify, commit_queryset):
    # type: (Notification, QuerySet) -> QuerySet
    """

    :param notify: Notification instance
    :param commit_queryset: QuerySet with Commit objects
    :return: commit_queryset: QuerySet with Commit objects
    """

    start_datetime = notify.extra_params.get('alert_commit_time_frame').get('value').get('start_datetime')
    end_datetime = notify.extra_params.get('alert_commit_time_frame').get('value').get('end_datetime')
    start_datetime = dateutil.parser.parse(start_datetime).time()
    end_datetime = dateutil.parser.parse(end_datetime).time()

    if start_datetime < end_datetime:
        commit_queryset = commit_queryset.filter(models.Q(timestamp__time__range=(start_datetime, end_datetime)))
    else:
        commit_queryset = commit_queryset.filter(~models.Q(timestamp__time__range=(start_datetime, end_datetime)))

    return commit_queryset


def commit_weekday(notify, commit_queryset):
    # type: (Notification, QuerySet) -> QuerySet
    """

    :param notify: Notification instance
    :param commit_queryset: QuerySet with Commit objects
    :return: commit_queryset: QuerySet with Commit objects
    """

    value_changed = notify.extra_params.get('alert_commit_weekday').get('value')

    commit_queryset = commit_queryset.filter(created__week_day__in=value_changed)

    return commit_queryset


def commit_changed_code(notify, commit_queryset):
    # type: (Notification, QuerySet) -> QuerySet
    """

    :param notify: Notification instance
    :param commit_queryset: QuerySet with Commit objects
    :return: commit_queryset: QuerySet with Commit objects
    """

    commit_queryset = Commit.objects.none()

    return commit_queryset


def check_updates(notify, date_range=None):
    # type: (Notification, tuple) -> None
    """
        Check updates for notification
    :param notify: Notification instance
    :param date_range: Tuple with datetime objects for one_off range
    :return:
    """

    alert_triggers = {
        'alert_areas': areas_changed_notification,
        'alert_committer': commits_has_not_change,
        'alert_lines': commit_lines_changed,
        'alert_files': commit_files_changed,
        'alert_authors': commit_authors_changed,
        'alert_commit_time_frame': commit_time_frame,
        'alert_commit_weekday': commit_weekday,
        'alert_commit_changed_code': commit_changed_code,
    }

    try:
        triggers_context = list()
        areas_prefetch = models.Prefetch('areas', queryset=Area.objects.exclude(name='Default Area'))
        files_prefetch = models.Prefetch('files', queryset=File.objects.all())
        for alert, value in notify.extra_params.items():
            if isinstance(value, dict):
                if value.get('enable'):
                    queryset = Commit.objects.filter(project=notify.project)
                    if not date_range:
                        previous_send_datetime = notify.previous_send_datetime.replace(tzinfo=pytz.timezone('UTC'))
                        queryset = queryset.filter(created__gt=previous_send_datetime)
                    else:
                        queryset = queryset.filter(created__date__range=date_range)
                    queryset = alert_triggers.get(alert)(notify, queryset)
                    if queryset.exists():

                        queryset = queryset.prefetch_related(areas_prefetch, files_prefetch)
                        trigger_context = {'commits': set(queryset),
                                           'alert': alert,
                                           'value': value.get('value')}
                        triggers_context.append(trigger_context)

        email_context = {}

        if len(triggers_context) > 0:
            emails = notify.emails.split(',')

            email_context['period'] = notify.get_period_display()
            email_context['triggers'] = triggers_context
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


def check_alerts_one_off(notify, date_range):
    # type: (Notification, tuple) -> None
    """
        Check updates for alert notification with one off period
    :param notify: Notification instance
    :param date_range: Tuple with datetime objects
    :return:
    """
    check_updates(notify, date_range)


def check_alerts_immediately(notify):
    # type: (Notification) -> None
    """
        Check updates for alert notification with immediately period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_alerts_daily(notify):
    # type: (Notification) -> None
    """
        Check updates for alert notification with daily period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_alerts_weekly(notify):
    # type: (Notification) -> None
    """
        Check updates for alert notification with weekly period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)


def check_alerts_fortnightly(notify):
    # type: (Notification) -> None
    """
        Check updates for alert notification with fortnightly period
    :param notify: Notification instance
    :return:
    """
    check_updates(notify)
