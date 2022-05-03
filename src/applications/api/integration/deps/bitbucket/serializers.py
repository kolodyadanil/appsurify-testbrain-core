# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rest_framework import serializers

from applications.integration.bitbucket.models import BitbucketRepository


class BitbucketRepositoryCreateListSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = BitbucketRepository
        exclude = ('user', 'social_token',)
