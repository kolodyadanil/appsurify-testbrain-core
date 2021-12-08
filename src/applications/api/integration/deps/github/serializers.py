# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rest_framework import serializers

from applications.integration.github.models import GithubRepository


class GithubRepositoryCreateListSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = GithubRepository
        exclude = ('user', 'token',)

# class GithubRepositoryGetTreeSerializer(serializers.Serializer):
#     project = serializers.IntegerField()
#     branch = serializers.CharField(max_length=255)
#     area = serializers.IntegerField(required=False)
#
#     class Meta(object):
#         pass
