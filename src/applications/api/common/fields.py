# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import copy
import inspect
import traceback
import time
import six
from django.db import transaction
from collections import OrderedDict

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from rest_framework.serializers import raise_errors_on_nested_writes
from rest_framework.utils import html, model_meta
from rest_framework.fields import ChoiceField


class ChoiceDisplayField(ChoiceField):
    def __init__(self, *args, **kwargs):
        self.display_only = kwargs.pop('display_only', False)
        super(ChoiceDisplayField, self).__init__(*args, **kwargs)
        self.choice_strings_to_display = {
            six.text_type(key): value for key, value in self.choices.items()
        }

    def to_representation(self, value):
        if value is None:
            return value
        if self.display_only:
            return self.choice_strings_to_display.get(six.text_type(value), value)
        return {
            'value': self.choice_strings_to_values.get(six.text_type(value), value),
            'display': self.choice_strings_to_display.get(six.text_type(value), value),
        }


class TimestampField(serializers.Field):
    def to_representation(self, value):
        return int(time.mktime(value.timetuple()))


class IntDurationField(serializers.DurationField):
    def to_representation(self, value):
        return value.total_seconds()