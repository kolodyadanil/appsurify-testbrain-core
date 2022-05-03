# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db.models.constants import LOOKUP_SEP
from rest_framework_filters import *
from django_filters.fields import Lookup

from applications.project.models import *
from applications.testing.models import *
from applications.vcs.models import *


class ProjectFilterSet(FilterSet):

    class Meta(object):
        model = Project
        fields = ()
