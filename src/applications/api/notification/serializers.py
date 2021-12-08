# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime

import pytz
from rest_framework import serializers

from applications.api.common.serializers import DynamicFieldsModelSerializer
from applications.notification.models import Notification
from applications.project.models import Project


class NotificationSerializer(DynamicFieldsModelSerializer):
    """
        Notification serializer
    """
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=True)

    period = serializers.IntegerField(allow_null=False, required=True)
    type = serializers.IntegerField(allow_null=False, required=True)
    extra_params = serializers.DictField(allow_null=False, required=True)

    emails = serializers.CharField(max_length=255, allow_blank=True, allow_null=False, required=True)

    schedule_hour = serializers.IntegerField(allow_null=True)
    schedule_weekday = serializers.IntegerField(allow_null=True)

    schedule_timezone = serializers.CharField(max_length=64, allow_null=True, required=True)
    schedule_last_send = serializers.HiddenField(default=datetime.datetime.now().replace(tzinfo=pytz.timezone('UTC')))

    one_off_start_date = serializers.DateField(allow_null=True)
    one_off_end_date = serializers.DateField(allow_null=True)

    class Meta(object):
        model = Notification
        fields = [
            'id', 'project', 'period', 'type', 'emails', 'schedule_hour', 'schedule_weekday', 'schedule_timezone',
            'extra_params', 'schedule_last_send', 'one_off_end_date', 'one_off_start_date']

    def validate_schedule_timezone(self, value):
        # type: (str) -> str
        """
        Validate schedule_timezone for None value
        :param value: CharField
        :return: value: CharField
        """
        if value is None:
            return 'UTC'
        return value
