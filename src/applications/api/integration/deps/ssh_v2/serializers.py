# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rest_framework import serializers

from applications.api.common.serializers import DynamicFieldsModelSerializer
from applications.integration.ssh_v2.models import GitSSHv2Repository


class GitSSHv2RepositoryCreateListSerializer(DynamicFieldsModelSerializer):

    class Meta(object):
        model = GitSSHv2Repository
        fields = '__all__'
