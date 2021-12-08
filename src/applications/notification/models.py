# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime

import pytz
from django.db import models
from django.db.models import JSONField

TIMEZONES = tuple(zip(pytz.all_timezones, pytz.all_timezones))


def relative_date(reference, weekday, timevalue):
    hour, minute = divmod(timevalue, 1)
    minute *= 60
    days = reference.weekday() - weekday
    return (reference - datetime.timedelta(days=days)).replace(
        hour=int(hour), minute=int(minute), second=0, microsecond=0)


def get_default_dict():
    default_dict = {
        "alert_commit_changed_code": {
            "enable": False,
            "value": None
        },
        "alert_authors": {
            "enable": False,
            "value": None
        },
        "alert_files": {
            "enable": False,
            "value": None
        },
        "alert_areas": {
            "enable": False,
            "value": None
        },
        "alert_committer": {
            "enable": False,
            "value": None
        },
        "alert_lines": {
            "enable": False,
            "value": None
        },
        "alert_commit_weekday": {
            "enable": False,
            "value": list()
        },
        "monitor_areas": list(),
        "monitor_files": list(),
        "alert_commit_time_frame": {
            "enable": False,
            "value": {
                "start_datetime": None,
                "end_datetime": None
            }
        },
    }
    return default_dict


class Notification(models.Model):
    """
    Notification Model.
    """

    PERIOD_IMMEDIATELY = 0
    PERIOD_DAILY = 1
    PERIOD_WEEKLY = 2
    PERIOD_FORTNIGHTLY = 3
    PERIOD_ONE_OFF = 4

    PERIOD_CHOICE = (
        (PERIOD_IMMEDIATELY, 'immediately'),
        (PERIOD_DAILY, 'daily'),
        (PERIOD_WEEKLY, 'weekly'),
        (PERIOD_FORTNIGHTLY, 'fortnightly'),
        (PERIOD_ONE_OFF, 'One Off')
    )

    TYPE_RISK = 0
    TYPE_ALERT = 1
    TYPE_DEFECT = 2
    TYPE_TEST_RUN = 3
    TYPE_MONITOR = 4
    TYPE_TEST_PRIORITIZATION = 5
    TYPE_RISK_ANALYSIS = 6

    TYPE_CHOICE = (
        (TYPE_RISK, 'risk'),
        (TYPE_ALERT, 'alert'),
        (TYPE_DEFECT, 'defect'),
        (TYPE_TEST_RUN, 'test run'),
        (TYPE_MONITOR, 'monitor'),
        (TYPE_TEST_PRIORITIZATION, 'test_prioritization'),
        (TYPE_RISK_ANALYSIS, 'risk_analysis'),
    )

    SCHEDULE_WEEKDAY_SUNDAY = 1
    SCHEDULE_WEEKDAY_MONDAY = 2
    SCHEDULE_WEEKDAY_TUESDAY = 3
    SCHEDULE_WEEKDAY_WEDNESDAY = 4
    SCHEDULE_WEEKDAY_THURSDAY = 5
    SCHEDULE_WEEKDAY_FRIDAY = 6
    SCHEDULE_WEEKDAY_SATURDAY = 7

    SCHEDULE_WEEKDAY_CHOICE = (
        (SCHEDULE_WEEKDAY_MONDAY, 'monday'),
        (SCHEDULE_WEEKDAY_TUESDAY, 'tuesday'),
        (SCHEDULE_WEEKDAY_WEDNESDAY, 'wednesday'),
        (SCHEDULE_WEEKDAY_THURSDAY, 'thursday'),
        (SCHEDULE_WEEKDAY_FRIDAY, 'friday'),
        (SCHEDULE_WEEKDAY_SATURDAY, 'saturday'),
        (SCHEDULE_WEEKDAY_SUNDAY, 'sunday')
    )

    project = models.ForeignKey('project.Project', related_name='notifications', blank=False, null=False,
                                on_delete=models.DO_NOTHING)

    period = models.IntegerField(default=PERIOD_IMMEDIATELY, choices=PERIOD_CHOICE, blank=True, null=False)
    type = models.IntegerField(default=TYPE_DEFECT, choices=TYPE_CHOICE, blank=True, null=False)
    extra_params = JSONField(default=get_default_dict, blank=True, null=False)

    emails = models.CharField(max_length=255, default='', blank=True, null=False)

    # TODO: add constraint in 'schedule_hour'
    schedule_hour = models.IntegerField(default=None, blank=True, null=True)
    schedule_weekday = models.IntegerField(default=SCHEDULE_WEEKDAY_MONDAY, choices=SCHEDULE_WEEKDAY_CHOICE, blank=True,
                                           null=True)

    schedule_timezone = models.CharField(max_length=64, choices=TIMEZONES, default='UTC')
    schedule_last_send = models.DateTimeField(default=None, blank=True, null=True)

    one_off_start_date = models.DateField(default=None, blank=True, null=True)
    one_off_end_date = models.DateField(default=None, blank=True, null=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta(object):
        verbose_name = u'Notification'
        verbose_name_plural = u'Notifications'
        indexes = [
            models.Index(fields=['-schedule_last_send']),
        ]
