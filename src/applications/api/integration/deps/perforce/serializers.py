# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rest_framework import serializers

from applications.api.common.serializers import DynamicFieldsModelSerializer
from applications.integration.perforce.models import PerforceRepository


class PerforceRepositoryCreateListSerializer(DynamicFieldsModelSerializer):

    class Meta(object):
        model = PerforceRepository
        exclude = ('user',)

