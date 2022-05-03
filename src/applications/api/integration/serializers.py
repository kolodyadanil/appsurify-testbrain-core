# -*- coding: utf-8 -*-

from rest_framework import serializers

from applications.api.common.serializers import DynamicFieldsModelSerializer
from applications.integration.github.models import GithubRepository
from applications.integration.bitbucket.models import BitbucketRepository
from applications.integration.perforce.models import PerforceRepository
from applications.integration.git.models import GitRepository
from applications.integration.ssh.models import GitSSHRepository
from applications.integration.ssh_v2.models import GitSSHv2Repository


class GithubRepositoryCreateListSerializer(serializers.ModelSerializer):

    class Meta(object):
        model = GithubRepository
        exclude = ('user', 'token',)


class BitbucketRepositoryCreateListSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = BitbucketRepository
        exclude = ('user', 'social_token',)


class PerforceRepositoryCreateListSerializer(DynamicFieldsModelSerializer):

    class Meta(object):
        model = PerforceRepository
        exclude = ('user',)


class GitRepositoryCreateListSerializer(DynamicFieldsModelSerializer):
    class Meta(object):
        model = GitRepository
        exclude = ('user', 'git_repository_name', 'port',)


class GitSSHRepositoryCreateListSerializer(DynamicFieldsModelSerializer):
    class Meta(object):
        model = GitSSHRepository
        exclude = ('repository_name',)


class GitSSHv2RepositoryCreateListSerializer(DynamicFieldsModelSerializer):
    class Meta(object):
        model = GitSSHv2Repository
        fields = '__all__'
