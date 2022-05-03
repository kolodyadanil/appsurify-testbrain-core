# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.generics import ListCreateAPIView, RetrieveDestroyAPIView
from rest_framework import viewsets, mixins
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from applications.organization.utils import get_current_organization
from applications.allauth.socialaccount.models import SocialToken
from rest_framework.decorators import action
from rest_framework.exceptions import *
from rest_framework.response import Response
from rest_framework.settings import api_settings
from applications.api.common.views import MultiSerializerViewSetMixin

from applications.api.integration.jira.serializers import *
from applications.integration.jira.models import *
from applications.integration.jira.tasks import *


User = get_user_model()


class JiraCredentialModelViewSet(viewsets.ModelViewSet):
    """
    JiraCredential API endpoint.
    ---
    list:
        List credential added by user into organization.


    """
    model = JiraCredential
    queryset = JiraCredential.objects.select_related('organization', 'user')

    serializer_class = JiraCredentialSerializer

    filter_class = None

    ordering_fields = ()
    search_fields = ()
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'jira_credential_pk'

    def get_queryset(self):
        queryset = super(JiraCredentialModelViewSet, self).get_queryset()
        queryset = queryset.filter(organization=get_current_organization(self.request), user=self.request.user)
        return queryset


class JiraProjectModelViewSet(viewsets.ModelViewSet):
    model = JiraProject
    queryset = JiraProject.objects.select_related('project', 'user')

    serializer_class = JiraProjectSerializer

    filter_class = None

    ordering_fields = ()
    search_fields = ()
    filter_fields = ()

    lookup_field = 'id'
    lookup_url_kwarg = 'jira_project_pk'

    def get_queryset(self):
        queryset = super(JiraProjectModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request), user=self.request.user)
        return queryset

    @action(methods=['GET'], detail=False, url_path=r'project/(?P<project_pk>[0-9]+)', url_name='GetByProject')
    def get_by_project(self, request, project_pk, **kwargs):
        try:
            instance = self.get_queryset().get(project_id=project_pk)
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except JiraProject.DoesNotExist:
            # raise APIException(detail='Project not found.')
            return Response({})
        # return Response({'status': True if issue else False}, status=status.HTTP_200_OK)

    @action(methods=['POST'], serializer_class=JiraProjectSyncSerializer, detail=False, url_path='pull', url_name='pull')
    def pull(self, request, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.data
        try:
            task = jira_pull_issues_task.delay(**data)
        except Exception as e:
            raise APIException(detail=e.message)
        return Response(data={'task_id': task.id, 'status': task.status}, status=status.HTTP_200_OK)

    @action(methods=['POST'], serializer_class=JiraProjectSyncSerializer, detail=False, url_path='push', url_name='push')
    def push(self, request, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.data
        try:
            task = jira_push_issues_task.delay(**data)
        except Exception as e:
            raise APIException(detail=e.message)
        return Response(data={'task_id': task.id, 'status': task.status}, status=status.HTTP_200_OK)


class JiraIssueModelViewSet(viewsets.ModelViewSet):
    model = JiraIssue

    queryset = JiraIssue.objects.select_related('defect', 'jira_project')

    serializer_class = JiraIssueSerializer

    filter_class = None

    ordering_fields = ()
    search_fields = ()
    filter_fields = ()

    lookup_field = 'id'
    lookup_url_kwarg = 'jira_issue_pk'

    def get_queryset(self):
        queryset = super(JiraIssueModelViewSet, self).get_queryset()
        queryset = queryset.filter(defect__project__organization=get_current_organization(self.request))
        return queryset

    @action(methods=['GET'], detail=False, url_path=r'defect/(?P<defect_pk>[0-9]+)', url_name='GetByDefect')
    def get_by_defect(self, request, defect_pk, **kwargs):
        try:
            defect = Defect.objects.get(id=defect_pk)
            instance = defect.jira_issue
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except Defect.DoesNotExist:
            raise APIException(detail='Defect not found.')
        except ObjectDoesNotExist:
            raise APIException(detail='Issue not found.')
        # return Response({'status': True if issue else False}, status=status.HTTP_200_OK)

    @action(methods=['POST'], serializer_class=JiraIssuePullSerializer, detail=False, url_path='pull', url_name='pull')
    def pull(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_pull(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_pull(self, serializer):
        serializer.pull()

    @action(methods=['POST'], serializer_class=JiraIssuePushSerializer, detail=False, url_path='push', url_name='push')
    def push(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_push(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_push(self, serializer):
        serializer.push()


