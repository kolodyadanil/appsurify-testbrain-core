# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rest_framework import serializers
from celery.result import AsyncResult

from applications.api.common.serializers import DynamicFieldsModelSerializer


class TaskResultSerializer(serializers.Serializer):
    status = serializers.ReadOnlyField()
    state = serializers.ReadOnlyField()
    result = serializers.ReadOnlyField()
    id = serializers.ReadOnlyField()
    task_id = serializers.ReadOnlyField()

    class Meta(object):
        fields = '__all__'
