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

from applications.api.integration.git.serializers import *
from applications.integration.git.events import event_commit, event_tag, event_delete
from applications.integration.git.hook import generate_hook
from applications.integration.git.utils import test_connection, install_hook, verify_secret_hook
from applications.integration.tasks import clone_repository_task
from applications.project.models import Project

User = get_user_model()


class GitRepositoryCreateAPIView(CreateAPIView):
    """
    Repository API endpoint
    ---
    create:
        Create repository endpoint


    """
    model = GitRepository
    serializer_class = GitRepositoryCreateListSerializer

    permission_classes = (IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        # try:
        #     if instance.clone_repository() is False:
        #         raise Exception("Can't clone repository")
        #     fetch_commits_task.delay(instance.id, None, GitRepository._meta.model_name)
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
        # return Response(data=serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        task = clone_repository_task.delay(instance.id, GitRepository._meta.model_name)
        return Response(data={'task_id': task.id, 'status': task.status}, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        user = self.request.user
        username = user.username

        try:
            project = Project.objects.get(id=self.request.data.get('project'))
        except (Project.DoesNotExist, Project.MultipleObjectsReturned):
            return Response({'detail': [_('Project not found')]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        repo_name = project.name
        git_repository_name = '{}/{}'.format(username, repo_name)
        if self.request.data.get('host').find(':') >= 0:
            host, port = self.request.data.get('host').split(':')
        else:
            host, port = self.request.data.get('host'), 22

        from applications.organization.utils import get_current_organization
        organization = get_current_organization(self.request)

        assert organization.is_member(user) is True

        instance = serializer.save(user=user, git_repository_name=git_repository_name, host=host, port=port)
        return instance


class GitRepositoryTestConnection(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = GitRepositoryTestConnectionSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.data.get('host').find(':') >= 0:
            host, port = serializer.data.get('host').split(':')
        else:
            host, port = serializer.data.get('host'), 22
        status_connection, message = test_connection(host=host,
                                                     user=serializer.data.get('login'),
                                                     password=serializer.data.get('password'),
                                                     port=port)
        if status_connection:
            return Response({'detail': [_('{}'.format(message))]}, status=status.HTTP_200_OK)
        else:
            return Response({'detail': [_('{}'.format(message))]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GitRepositoryGenerateHook(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = GitRepositoryHookSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            repository_credential = GitRepository.objects.get(project_id=serializer.data.get('project'))
        except GitRepository.DoesNotExist:
            return Response({'detail': [_('Project not found')]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        username, repos_name = repository_credential.git_repository_name.split('/')
        scheme = request.stream.scheme
        domain = '{}://{}'.format(scheme, get_current_site(request))
        template = generate_hook(domain=domain, username=username, repos_name=repos_name,
                                 project_id=repository_credential.project_id)
        return Response(data=template, content_type='text/plain')


class GitRepositoryInstallHook(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = GitRepositoryHookSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            repository_credential = GitRepository.objects.get(project_id=serializer.data.get('project'))
        except GitRepository.DoesNotExist:
            return Response({'detail': [_('Project not found')]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        username, repos_name = repository_credential.git_repository_name.split('/')
        scheme = request.scheme
        domain = '{}://{}'.format(scheme, get_current_site(request))
        hook = generate_hook(domain=domain, username=username, repos_name=repos_name,
                             project_id=repository_credential.project_id)

        status_connection, message = install_hook(host=repository_credential.host,
                                                  login=repository_credential.login,
                                                  password=repository_credential.password,
                                                  port=repository_credential.port,
                                                  path=repository_credential.path,
                                                  hook=hook,
                                                  force=serializer.data.get('force'))

        if status_connection:
            repository_credential.is_installed_hook = True
            repository_credential.save()
            return Response({'detail': [_('{}'.format(message))]}, status=status.HTTP_200_OK)
        else:
            repository_credential.is_installed_hook = False
            repository_credential.save()
            return Response({'detail': [_('{}'.format(message))]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GitHookRequests(APIView):
    permission_classes = (AllowAny,)
    events = {
        'push': event_commit,
        'create': event_tag,
        'delete': event_delete,
    }

    def post(self, request, *args, **kwargs):
        verify, response = verify_secret_hook(request)
        if not verify:
            return response

        event = request.META.get('HTTP_X_GIT_EVENT')
        if event in self.events.keys():
            self.events.get(event)(request.data, kwargs.get('project_id'))
            return HttpResponse(status=200)

        return HttpResponse(status=204)
