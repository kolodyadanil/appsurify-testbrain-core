# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db.models.constants import LOOKUP_SEP
from rest_framework_filters import *
from django_filters.fields import Lookup


class BaseFilterSet(FilterSet):

    def __init__(self, data=None, *args, **kwargs):
        # if filterset is bound, use initial values as defaults
        if data is not None:
            # get a mutable copy of the QueryDict
            data = data.copy()

            for name, f in self.base_filters.items():
                initial = f.extra.get('initial')

                # filter param is either missing or empty, use initial as default
                if not data.get(name) and initial:
                    data[name] = initial

        super(BaseFilterSet, self).__init__(data, *args, **kwargs)