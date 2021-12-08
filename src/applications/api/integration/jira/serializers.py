# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core.exceptions import ObjectDoesNotExist

from rest_framework import serializers
from applications.organization.utils import get_current_organization
from applications.project.models import Project
from applications.integration.jira.models import *

from applications.api.common.serializers import CurrentUserDefault, CurrentOrganizationDefault


class JiraCredentialSerializer(serializers.ModelSerializer):
    organization = serializers.HiddenField(default=CurrentOrganizationDefault())
    user = serializers.HiddenField(default=CurrentUserDefault())

    url = serializers.URLField(write_only=True)
    username = serializers.CharField(write_only=True)
    token = serializers.CharField(write_only=True)

    domain = serializers.ReadOnlyField()
    projects = serializers.ReadOnlyField(source='get_projects', allow_null=True)
    issue_types = serializers.ReadOnlyField(source='get_issue_types', allow_null=True)

    class Meta(object):
        model = JiraCredential
        fields = ['id', 'organization', 'user', 'url', 'username', 'token', 'domain', 'projects', 'issue_types', ]
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=model.objects.all(),
                fields=('organization', 'user', 'url'),
                message='You already added this Jira server.'
            )
        ]

    def validate(self, attrs):
        attrs = super(JiraCredentialSerializer, self).validate(attrs=attrs)

        organization = attrs['organization']
        user = attrs['user']

        if organization is None:
            raise serializers.ValidationError({'organization': 'Organization for this domain not found.'})

        if not organization.is_member(user):
            raise serializers.ValidationError(
                {'user': 'User `{username}` is not a member of the organization.'.format(username=user.username)})

        url = attrs['url']
        username = attrs['username']
        token = attrs['token']

        result = JiraCredential.test_connection(url, username, token)

        if result in [401, 403]:
            raise serializers.ValidationError({
                'credentials': 'Your authentication information is incorrect. Please try again.',
            })
        elif result == 404:
            raise serializers.ValidationError({
                'url': 'Your jira server not found. Please try again.',
            })
        elif result != 200:
            raise serializers.ValidationError({
                'credentials': 'Your jira server return `status_code {result}`. Please try again.'.format(result=result)
            })

        return attrs


class JiraProjectSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=CurrentUserDefault())
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=True)
    credential = serializers.PrimaryKeyRelatedField(queryset=JiraCredential.objects.all(), required=True)

    extra_data = serializers.DictField(allow_null=False, required=True)

    class Meta(object):
        model = JiraProject
        fields = ['id', 'user', 'project', 'credential', 'extra_data', ]
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=model.objects.all(),
                fields=('project', 'credential'),
                message='You already connected this Jira server.'
            )
        ]

    def _validate_own_credential(self, user, credential):
        if user != credential.user:
            raise serializers.ValidationError({'user': 'Current user not a credential owner.'})
        return user

    def _validate_jira_project(self, jira_project):
        if 'id' not in jira_project:
            raise serializers.ValidationError({'jira_project': 'missing `id` key.'})
        if 'key' not in jira_project:
            raise serializers.ValidationError({'jira_project': 'missing `key` key.'})
        if 'name' not in jira_project:
            raise serializers.ValidationError({'jira_project': 'missing `name` key.'})
        return jira_project

    def _validate_jira_issue_types(self, jira_issue_types):
        if not isinstance(jira_issue_types, (list, tuple)):
            raise serializers.ValidationError({'jira_issue_types': 'not a list'})
        for issue_type in jira_issue_types:
            if 'id' not in issue_type:
                raise serializers.ValidationError({'jira_issue_types': 'One or more missing `id` key.'})
            if 'name' not in issue_type:
                raise serializers.ValidationError({'jira_issue_types': 'One or more missing `name` key.'})
        return jira_issue_types

    def _validate_extra_data(self, extra_data):
        if 'project' not in extra_data:
            raise serializers.ValidationError({'extra_data': 'missing `project` key.'})
        if 'issue_types' not in extra_data:
            raise serializers.ValidationError({'extra_data': 'missing `project` key.'})
        self._validate_jira_project(extra_data['project'])
        self._validate_jira_issue_types(extra_data['issue_types'])
        return extra_data

    def validate(self, attrs):
        attrs = super(JiraProjectSerializer, self).validate(attrs=attrs)
        self._validate_extra_data(attrs['extra_data'])
        self._validate_own_credential(attrs['user'], attrs['credential'])
        return attrs


class JiraProjectSyncSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=True)
    force_update = serializers.BooleanField(default=False, write_only=True)

    class Meta(object):
        model = JiraProject
        fields = ['project', 'force_update']

    def to_representation(self, instance):
        representation_value = super(JiraProjectSyncSerializer, self).to_representation(instance)
        representation_value.update({
            "force_update": instance['force_update']
        })
        return representation_value


class JiraIssueSerializer(serializers.ModelSerializer):
    defect = serializers.PrimaryKeyRelatedField(queryset=Defect.objects.all(), required=False)
    jira_project = serializers.PrimaryKeyRelatedField(queryset=JiraProject.objects.all(), required=True)

    class Meta(object):
        model = JiraIssue
        fields = ['defect', 'jira_project', 'issue_id', 'extra_data']


class JiraIssuePullSerializer(serializers.ModelSerializer):
    defect = serializers.PrimaryKeyRelatedField(queryset=Defect.objects.all(), required=True)

    class Meta(object):
        model = JiraIssue
        fields = ['defect']

    def _validate_defect_issue(self, defect):
        try:
            issue = defect.jira_issue
        except ObjectDoesNotExist:
            raise serializers.ValidationError({'defect': 'Defect has no associated Jira Issue. You must first push.'})
        return issue

    def _validate_jira_project(self, defect):
        try:
            jira_project = defect.project.jira_project
        except ObjectDoesNotExist:
            raise serializers.ValidationError({'defect': 'Project has no associated Jira Project.'})
        return jira_project

    def validate(self, attrs):
        attrs = super(JiraIssuePullSerializer, self).validate(attrs=attrs)
        self._validate_defect_issue(attrs['defect'])
        attrs['jira_project'] = self._validate_jira_project(attrs['defect'])
        return attrs

    def pull(self, **kwargs):
        jira_project = self.validated_data['jira_project']
        defect = self.validated_data['defect']
        issue = defect.jira_issue
        instance = JiraIssue.pull_issue(jira_project, issue.extra_data, defect=defect)
        return instance


class JiraIssuePushSerializer(serializers.ModelSerializer):
    defect = serializers.PrimaryKeyRelatedField(queryset=Defect.objects.all(), required=True)

    class Meta(object):
        model = JiraIssue
        fields = ['defect']

    def _validate_jira_project(self, defect):
        try:
            jira_project = defect.project.jira_project
        except ObjectDoesNotExist:
            raise serializers.ValidationError({'defect': 'Project has no associated Jira Project.'})
        return jira_project

    def validate(self, attrs):
        attrs = super(JiraIssuePushSerializer, self).validate(attrs=attrs)
        attrs['jira_project'] = self._validate_jira_project(attrs['defect'])
        return attrs

    def push(self, **kwargs):
        jira_project = self.validated_data['jira_project']
        defect = self.validated_data['defect']

        instance = JiraIssue.push_issue(jira_project, defect)
        return instance
