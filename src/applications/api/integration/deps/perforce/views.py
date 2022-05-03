# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.auth import get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _
from rest_framework import status
from rest_framework.generics import GenericAPIView, CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from applications.integration.tasks import fetch_commits_task, update_perforce_repository, clone_repository_task
from applications.project.models import Project
from applications.integration.perforce.models import PerforceRepository
from applications.integration.perforce.events import event_push

from .serializers import PerforceRepositoryCreateListSerializer


User = get_user_model()


class PerforceRepositoryCreateAPIView(CreateAPIView):
    """
    Repository API endpoint
    ---
    create:
        Create repository endpoint


    """
    model = PerforceRepository
    serializer_class = PerforceRepositoryCreateListSerializer

    permission_classes = (IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        # try:
        #     update_perforce_repository.delay(repository_id=instance.id)
        # except Exception as error:
        #     from django.conf import settings
        #     instance.delete()
        #     if settings.DEBUG:
        #         return Response(data={'detail': [_('{}'.format(error))]},
        #                         status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        #     return Response(data={'detail': [_('{}'.format(
        #         'Repository isn`t cloned or cloned with errors, contact the administrator'))]},
        #         status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # headers = self.get_success_headers(serializer.data)
        # return Response(data=serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        task = update_perforce_repository.delay(repository_id=instance.id)
        return Response(data={'task_id': task.id, 'status': task.status}, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        user = self.request.user

        try:
            project = Project.objects.get(id=self.request.data.get('project'))
        except (Project.DoesNotExist, Project.MultipleObjectsReturned):
            return Response({'detail': [_('Project not found')]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        from applications.organization.utils import get_current_organization
        organization = get_current_organization(self.request)

        assert organization.is_member(user) is True

        instance = serializer.save(user=user, project=project)
        return instance


class PerforceHookRequests(APIView):
    permission_classes = (AllowAny,)

    def get(self, request, *args, **kwargs):
        event_push(kwargs.get('project_id'))
        return HttpResponse(status=200)

    def post(self, request, *args, **kwargs):
        event_push(kwargs.get('project_id'))
        return HttpResponse(status=200)
