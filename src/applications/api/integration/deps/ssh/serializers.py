# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from applications.api.common.serializers import DynamicFieldsModelSerializer
from applications.integration.ssh.models import GitSSHRepository


class GitSSHRepositoryCreateListSerializer(DynamicFieldsModelSerializer):
    class Meta(object):
        model = GitSSHRepository
        exclude = ('repository_name',)
