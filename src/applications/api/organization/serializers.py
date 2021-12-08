# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import copy
import inspect
import traceback

from collections import OrderedDict

from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from rest_framework import serializers


from applications.organization.models import *


class OrganizationSerializer(serializers.ModelSerializer):

    class Meta(object):
        model = Organization
        fields = '__all__'
