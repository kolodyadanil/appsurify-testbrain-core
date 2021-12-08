# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import operator
from functools import reduce

from django.db import models
import six
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.compat import distinct
from rest_framework.filters import SearchFilter


class MultiFilterClassBackendMixin(object):

    def filter_queryset(self, request, queryset, view, default=False):
        filter_class = self.get_filter_class(view, queryset, default=default)

        if filter_class:
            return filter_class(request.query_params, queryset=queryset, request=request).qs

        return queryset

    def get_filter_class(self, view, queryset=None, default=False):
        if default:
            filter_class = getattr(view, 'filter_class', None)
            filter_fields = getattr(view, 'filter_fields', None)

            if filter_class:
                filter_model = filter_class.Meta.model

                assert issubclass(queryset.model, filter_model), \
                    'FilterSet model %s does not match queryset model %s' % \
                    (filter_model, queryset.model)

                return filter_class
        else:
            action = getattr(view, 'action', None)
            try:
                filter_class = getattr(view, 'filter_action_classes', None)[action]
            except (KeyError, AttributeError, TypeError):
                filter_class = getattr(view, 'filter_class', None)

                # TODO: Need create validation
                filter_fields = getattr(view, 'filter_fields', None)

                if filter_class:
                    filter_model = filter_class.Meta.model

                    assert issubclass(queryset.model, filter_model), \
                        'FilterSet model %s does not match queryset model %s' % \
                        (filter_model, queryset.model)

                    return filter_class

            return filter_class


class MultiFilterClassBackend(MultiFilterClassBackendMixin, DjangoFilterBackend):
    pass


class MultiSearchFilterClassMixin(object):
    def filter_queryset(self, request, queryset, view, default=False):
        action = getattr(view, 'action', None)
        try:
            search_fields = getattr(view, 'search_action_fields', None)[action]
        except (KeyError, AttributeError, TypeError):
            search_fields = getattr(view, 'search_fields', None)

        search_terms = self.get_search_terms(request)

        if not search_fields or not search_terms:
            return queryset

        orm_lookups = [
            self.construct_search(six.text_type(search_field))
            for search_field in search_fields
        ]

        base = queryset
        conditions = []
        for search_term in search_terms:
            queries = [
                models.Q(**{orm_lookup: search_term})
                for orm_lookup in orm_lookups
            ]
            conditions.append(reduce(operator.or_, queries))
        queryset = queryset.filter(reduce(operator.and_, conditions))

        if self.must_call_distinct(queryset, search_fields):
            # Filtering against a many-to-many field requires us to
            # call queryset.distinct() in order to avoid duplicate items
            # in the resulting queryset.
            # We try to avoid this if possible, for performance reasons.
            queryset = distinct(queryset, base)
        return queryset


class SearchMultiFilterClass(MultiSearchFilterClassMixin, SearchFilter):
    pass


