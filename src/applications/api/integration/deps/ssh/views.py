# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import base64

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from applications.api.integration.ssh.serializers import GitSSHRepositoryCreateListSerializer
from applications.integration.ssh.events import event_push
from applications.integration.ssh.models import GitSSHRepository
from applications.integration.tasks import clone_repository_task

User = get_user_model()


class GitSSHRepositoryViewSet(viewsets.ModelViewSet):
    """
    Repository API endpoint
    ---
    create:
        Create repository endpoint


    """
    model = GitSSHRepository
    queryset = GitSSHRepository.objects.all()
    serializer_class = GitSSHRepositoryCreateListSerializer

    permission_classes = (IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        private_key_file = request.FILES.get('private_key')
        private_key = base64.encodestring(private_key_file.file.read())
        data['private_key'] = private_key
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        # try:
        #     instance.clone_repository()
        #     fetch_commits_task.delay(instance.id, None, GitSSHRepository._meta.model_name)
        # except Exception as error:
        #     from django.conf import settings
        #     instance.delete()
        #     if settings.DEBUG:
        #         return Response(data={'detail': [_('{}'.format(error))]},
        #                         status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        #     return Response(data={'detail': [_('{}'.format(
        #         'Repository isn`t cloned or cloned with errors, contact the administrator'))]},
        #         status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        #
        # headers = self.get_success_headers(serializer.data)
        # return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        task = clone_repository_task.delay(instance.id, GitSSHRepository._meta.model_name)
        return Response(data={'task_id': task.id, 'status': task.status}, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        return serializer.save()


class GitSSHHookRequests(APIView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        event_push(kwargs.get('project_id'))
        return HttpResponse(status=200)
