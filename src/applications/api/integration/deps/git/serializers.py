# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rest_framework import serializers

from applications.api.common.serializers import DynamicFieldsModelSerializer
from applications.integration.git.models import GitRepository


class GitRepositoryCreateListSerializer(DynamicFieldsModelSerializer):
    class Meta(object):
        model = GitRepository
        exclude = ('user', 'git_repository_name', 'port',)


class GitRepositoryHookSerializer(serializers.Serializer):
    project = serializers.IntegerField()
    force = serializers.BooleanField(default=False)

    class Meta(object):
        pass


class GitRepositoryTestConnectionSerializer(serializers.Serializer):
    host = serializers.CharField(max_length=255)
    login = serializers.CharField(max_length=255)
    password = serializers.CharField(max_length=255)
    port = serializers.IntegerField(read_only=True)

    class Meta(object):
        pass

# class GitRepositoryGetTreeSerializer(serializers.Serializer):
#     project = serializers.IntegerField()
#     branch = serializers.CharField(max_length=255)
#     area = serializers.IntegerField(required=False)
#
#     class Meta(object):
#         pass
