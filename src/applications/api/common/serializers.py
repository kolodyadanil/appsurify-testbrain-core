# -*- coding: utf-8 -*-
import copy
import importlib
import inspect
import traceback
import time
import six
from django.db import transaction
from collections import OrderedDict
from rest_framework import ISO_8601

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from rest_framework.serializers import raise_errors_on_nested_writes
from rest_framework.utils import html, model_meta

from applications.api.common.fields import (
    ChoiceDisplayField, TimestampField, IntDurationField
)
from applications.api.common.utils import split_levels
from applications.organization.utils import get_current_organization

# support basestring in python3
try:
    unicode = unicode
except NameError:
    # 'unicode' is undefined, must be Python 3
    str = str
    unicode = str
    bytes = bytes
    basestring = (str,bytes)
else:
    # 'unicode' exists, must be Python 2
    str = str
    unicode = unicode
    bytes = str
    basestring = basestring

class CurrentUserDefault(object):
    def set_context(self, serializer_field):
        self.user = serializer_field.context['request'].user

    def __call__(self):
        return self.user

    def __repr__(self):
        return '%s()' % self.__class__.__name__


class CurrentOrganizationDefault(object):
    def set_context(self, serializer_field):
        self.organization = get_current_organization(serializer_field.context['request'])

    def __call__(self):
        return self.organization

    def __repr__(self):
        return '%s()' % self.__class__.__name__


class DynamicFieldsModelSerializer(serializers.ModelSerializer):

    def __init__(self, *args, **kwargs):

        fields = None

        if fields is None:
            # Don't pass the 'fields' arg up to the superclass
            fields = kwargs.pop('fields', None)

        super(DynamicFieldsModelSerializer, self).__init__(*args, **kwargs)

        if self.context.get('request'):
            try:
                fields = self.context['request'].query_params.get('fields', None)
            except AttributeError:
                fields = None

        if fields is not None:
            if not isinstance(fields, (list, tuple)):
                fields = fields.split(',')
            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields.keys())
            for field_name in existing - allowed:
                self.fields.pop(field_name)


class DynamicFieldsRelatedSerializer(serializers.RelatedField):
    fields = '__all__'
    pk_name = 'id'
    force_pk_only = False

    def __init__(self, **kwargs):
        self.fields = kwargs.pop('fields', '__all__')
        self.pk_name = kwargs.pop('pk_name', 'id')
        self.pk_field = kwargs.pop('pk_field', None)
        super(DynamicFieldsRelatedSerializer, self).__init__(**kwargs)

    @property
    def _meta(self):
        return self.Meta

    def to_internal_value(self, data):
        if self.pk_field is not None:
            data = self.pk_field.to_internal_value(data)

        try:
            if isinstance(data, dict) and data.has_key(self.pk_name):
                data = self.get_queryset().get(pk=data[self.pk_name])
            else:
                data = self.get_queryset().get(pk=data)
            return data
        except ObjectDoesNotExist:
            self.fail('does_not_exist', pk_value=data)
        except (TypeError, ValueError):
            self.fail('incorrect_type', data_type=type(data).__name__)

    def to_representation(self, value, force_pk_only=False):
        if self.pk_field is not None:
            return self.pk_field.to_representation(value.pk)
        if not self.use_pk_only_optimization() and not isinstance(value, bool) and not force_pk_only:
            serializer = self._meta.model_serializer_class
            value = serializer(value, fields=self.fields, read_only=True).data
        elif self.use_pk_only_optimization() or force_pk_only:
            value = getattr(value, self.pk_name)
        else:
            value = value
        return value

    def get_choices(self, cutoff=None):
        queryset = self.get_queryset()
        if queryset is None:
            # Ensure that field.choices returns something sensible
            # even when accessed with a read-only field.
            return {}

        if cutoff is not None:
            queryset = queryset[:cutoff]

        return OrderedDict([
            (
                self.to_representation(item, force_pk_only=True),
                self.display_value(item)
            )
            for item in queryset
        ])


class FlexFieldsSerializerMixin(object):
    expandable_fields = {}

    def __init__(self, *args, **kwargs):
        self.expanded_fields = []

        passed = {
            'expand': kwargs.pop('expand', []),
            'fields': kwargs.pop('fields', []),
            'omit': kwargs.pop('omit', []),
        }


        super(FlexFieldsSerializerMixin, self).__init__(*args, **kwargs)
        expand = self._get_expand_input(passed)
        fields = self._get_fields_input(passed)
        omit = self._get_omit_input(passed)

        expand_fields, next_expand_fields = split_levels(expand)
        sparse_fields, next_sparse_fields = split_levels(fields)
        omit_fields, next_omit_fields = split_levels(omit)

        self._clean_fields(omit_fields, sparse_fields, next_omit_fields)

        expanded_field_names = self._get_expanded_names(expand_fields, omit_fields, sparse_fields, next_omit_fields)

        for name in expanded_field_names:

            self.expanded_fields.append(name)

            self.fields[name] = self._make_expanded_field_serializer(
                name, next_expand_fields, next_sparse_fields, next_omit_fields
            )

    def _make_expanded_field_serializer(self, name, nested_expand, nested_fields, nested_omit):

        field_options = self.expandable_fields[name]
        serializer_class = field_options[0]
        serializer_settings = copy.deepcopy(field_options[1])

        if name in nested_expand:
            serializer_settings['expand'] = nested_expand[name]

        if name in nested_fields:
            serializer_settings['fields'] = nested_fields[name]

        if name in nested_omit:
            serializer_settings["omit"] = nested_omit[name]

        if serializer_settings.get('source') == name:
            del serializer_settings['source']

        if type(serializer_class) == unicode:
            serializer_class = self._import_serializer_class(serializer_class)

        return serializer_class(**serializer_settings)

    def _import_serializer_class(self, location):

        pieces = location.split('.')
        class_name = pieces.pop()

        module = importlib.import_module('.'.join(pieces))
        return getattr(module, class_name)

    def _clean_fields(self, omit_fields, sparse_fields, next_level_omits):

        sparse = len(sparse_fields) > 0
        to_remove = []

        if not sparse and len(omit_fields) == 0:
            return

        for field_name in self.fields:
            is_present = self._should_field_exist(
                field_name, omit_fields, sparse_fields, next_level_omits
            )

            if not is_present:
                to_remove.append(field_name)

        for remove_field in to_remove:
            self.fields.pop(remove_field)

    def _should_field_exist(
            self, field_name, omit_fields, sparse_fields, next_level_omits
    ):

        if field_name in omit_fields and field_name not in next_level_omits:
            return False

        if len(sparse_fields) > 0 and field_name not in sparse_fields:
            return False

        return True

    def _get_expanded_names(self, expand_fields, omit_fields, sparse_fields, next_level_omits):

        if len(expand_fields) == 0:
            return []

        if "~all" in expand_fields or "*" in expand_fields:
            expand_fields = self.expandable_fields.keys()

        accum = []

        for name in expand_fields:
            if name not in self.expandable_fields:
                continue

            if not self._should_field_exist(
                name, omit_fields, sparse_fields, next_level_omits
            ):
                continue

            accum.append(name)

        return accum

    @property
    def _can_access_request(self):

        if self.parent:
            return False

        if not hasattr(self, 'context') or not self.context.get('request', None):
            return False

        flex = getattr(self.context['request'], 'flex') if hasattr(self.context['request'], 'flex') else False

        return self.context['request'].method == 'GET' or flex

    def _get_omit_input(self, passed_settings):
        value = passed_settings.get('omit')

        if len(value) > 0:
            return value

        return self._parse_request_list_value('omit')

    def _get_fields_input(self, passed_settings):
        value = passed_settings.get('fields')

        if len(value) > 0:
            return value

        return self._parse_request_list_value('fields')

    def _get_expand_input(self, passed_settings):
        value = passed_settings.get('expand')

        if len(value) > 0:
            return value

        expand = self._parse_request_list_value('expand')

        if "permitted_expands" in self.context:
            permitted_expands = self.context["permitted_expands"]

            if "~all" in expand or "*" in expand:
                return permitted_expands
            else:
                return list(set(expand) & set(permitted_expands))

        return expand

    def _parse_request_list_value(self, field):
        if not self._can_access_request:
            return []

        value = self.context["request"].query_params.get(field)
        return value.split(",") if value else []