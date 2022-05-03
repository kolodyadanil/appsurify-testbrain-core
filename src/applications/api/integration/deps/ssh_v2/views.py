# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

from django.contrib.auth import get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _
from django.template.defaultfilters import slugify

from rest_framework import status
from rest_framework.exceptions import APIException, AuthenticationFailed, PermissionDenied
from rest_framework.generics import GenericAPIView, CreateAPIView, ListCreateAPIView, ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from applications.api.external.utils import ConfirmationHMAC

from applications.api.integration.ssh_v2.serializers import *

from applications.integration.ssh_v2.events import event_commit, event_tag, event_delete, event_install
from applications.integration.ssh_v2.hook import generate_hook
# from applications.integration.ssh_v2.utils import install_hook, verify_secret_hook

from applications.integration.tasks import fetch_commits_task
from applications.organization.utils import get_current_organization
from applications.project.models import Project

from applications.project.permissions import IsOwner
from .permissions import IsAuthenticatedToken


User = get_user_model()


class GitSSHv2RepositoryRetrieveAPIView(RetrieveAPIView):
    """
    Repository API endpoint
    ---
    list:
        List repository endpoint


    """
    model = GitSSHv2Repository
    serializer_class = GitSSHv2RepositoryCreateListSerializer

    permission_classes = (IsAuthenticated,)

    queryset = GitSSHv2Repository.objects.all()



class GitSSHv2RepositoryCreateAPIView(CreateAPIView):
    """
    Repository API endpoint
    ---
    create:
        Create repository endpoint


    """
    model = GitSSHv2Repository
    serializer_class = GitSSHv2RepositoryCreateListSerializer

    permission_classes = (IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        user = self.request.user
        username = user.username

        try:
            project = Project.objects.get(id=self.request.data.get('project'))
        except (Project.DoesNotExist, Project.MultipleObjectsReturned):
            return Response({'detail': [_('Project not found')]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        repository_name = slugify(project.name)

        from applications.organization.utils import get_current_organization
        organization = get_current_organization(self.request)

        if not organization.is_member(user):
            raise PermissionDenied('Invalid current user')

        data = request.data.copy()
        data['user'] = user.pk
        data['project'] = project.pk
        data['repository_name'] = repository_name

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(data=serializer.data, status=status.HTTP_201_CREATED)


class GitSSHv2RepositoryGenerateHook(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, project_id, *args, **kwargs):
        project = Project.objects.get(id=project_id)
        repository = project.git_ssh_v2_repository
        organization = get_current_organization(request=request)
        hook_url = request.build_absolute_uri(reverse('git-ssh-v2-hook', args=(project_id, )))
        username = repository.user.username
        repo_name = repository.repository_name
        api_key = ConfirmationHMAC(organization).key

        data = generate_hook(hook_url, username, repo_name, api_key)
        response = HttpResponse(status=status.HTTP_200_OK, content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename="install.py"'
        response.write(data)
        return response


class GitSSHv2HookRequests(APIView):
    permission_classes = (IsAuthenticatedToken,)

    events = {
        'install': event_install,
        'push': event_commit,
        'create': event_tag,
        'delete': event_delete,
    }

    def post(self, request, project_id, *args, **kwargs):
        token = self.request.META.get('HTTP_TOKEN', None)

        organization_from_token = ConfirmationHMAC.from_key(token)
        organization = get_current_organization(request)

        if organization != organization_from_token:
            raise AuthenticationFailed()

        event = request.META.get('HTTP_X_GIT_EVENT')
        if event in self.events.keys():
            result = self.events.get(event)(request.data, project_id)
            if result:
                return HttpResponse(content='success', status=status.HTTP_200_OK)
            else:
                return HttpResponse(content='reset', status=status.HTTP_205_RESET_CONTENT)

        return HttpResponse(content='method not allowed', status=status.HTTP_405_METHOD_NOT_ALLOWED)


