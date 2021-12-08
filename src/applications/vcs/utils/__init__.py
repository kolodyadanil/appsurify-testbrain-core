# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from six import string_types
from importlib import import_module
from django.db.models import Min, Max
from django.utils import timezone
import six


def import_callable(path_or_callable):
    if hasattr(path_or_callable, '__call__'):
        return path_or_callable
    else:
        assert isinstance(path_or_callable, string_types)
        package, attr = path_or_callable.rsplit('.', 1)
        return getattr(import_module(package), attr)


def create_date_list(queryset):
    qs = queryset.aggregate(min_date=Min('created'), max_date=Max('created'))
    min_date = qs['min_date']
    max_date = qs['max_date']

    for index in list(range((max_date-min_date).days + 2)):
        yield (min_date + timezone.timedelta(index)).date()


def get_next_or_prev(models, item, direction):
    # type: (object, object, object) -> object
    '''

    # Declare our item
    store = Store.objects.get(pk=pk)
    # Define our models
    stores = Store.objects.all()
    # Ask for the next item
    new_store = get_next_or_prev(stores, store, 'next')
    # If there is a next item
    if new_store:
        # Replace our item with the next one
        store = new_store

    Returns the next or previous item of
    a query-set for 'item'.
    'models' is a query-set containing all
    items of which 'item' is a part of.
    direction is 'next' or 'prev'
    '''
    getit = False

    if direction == 'prev':
        models = models.reverse()

    for m in models:
        if getit:
            return m
        if item == m:
            getit = True

    if getit:
        # This would happen when the last
        # item made getit True
        return models[0]
    return False


