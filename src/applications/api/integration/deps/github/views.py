# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveDestroyAPIView
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from applications.allauth.socialaccount.models import SocialToken, SocialAccount
from applications.api.integration.github.serializers import GithubRepositoryCreateListSerializer
from applications.integration.github.api import get_full_list_repos
from applications.integration.github.events import event_create, event_push, event_issue, event_delete
from applications.integration.github.models import GithubRepository
from applications.integration.github.utils import verify_secret_hook
from applications.integration.tasks import clone_repository_task
from applications.organization.utils import get_current_organization

User = get_user_model()


class GithubRepositoryFullListAPIView(APIView):
    """
    Repository list from Github endpoint
    ---
    list:
        List repository from github endpoint


    """

    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        try:
            token_obj = SocialToken.objects.get(account__id=request.query_params.get('id', None),
                                                   app__provider='github')
        except SocialToken.DoesNotExist:
            return Response({'detail': [_('Access token does not exists')]},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        from github import BadCredentialsException, GithubException

        try:
            list_repos = get_full_list_repos(token_obj.token)
            return Response({'repos': list_repos}, status=status.HTTP_200_OK)
        except BadCredentialsException as exc:
            response_info = {
                    'detail': [_('Token is not valid. Please reconnect to "github".')],
                    'is_bad_credentials': True,
            }
            return Response(response_info, status.HTTP_500_INTERNAL_SERVER_ERROR)
        except GithubException as exc:
            return Response(exc.data, status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as exc:
            return Response(exc.message, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GithubRepositoryCreateListAPIView(ListCreateAPIView):
    """
    Repository API endpoint
    ---
    list:
        List repository endpoint


    create:
        Create repository endpoint


    """
    model = GithubRepository
    queryset = GithubRepository.objects.all()
    serializer_class = GithubRepositoryCreateListSerializer

    permission_classes = (IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)

        # try:
        #     instance.clone_repository()
        #     fetch_commits_task.delay(instance.id, {}, GithubRepository._meta.model_name)
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
        task = clone_repository_task.delay(instance.id, GithubRepository._meta.model_name)
        return Response(data={'task_id': task.id, 'status': task.status}, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        organization = get_current_organization(self.request)
        user = self.request.user
        assert organization.is_member(user) is True
        token = SocialAccount.objects.filter(provider='github',
                                             user=user).first().socialtoken_set.first().token
        instance = serializer.save(user=user, token=token)
        return instance


class GithubRepositoryRetrieveDestroyAPIView(RetrieveDestroyAPIView):
    """
    Repository API endpoint
    ---
    retrieve:
        Retrieve repository endpoint


    delete:
        Delete repository endpoint


    """
    serializer_class = GithubRepositoryCreateListSerializer
    queryset = GithubRepository.objects.all()
    permission_classes = (IsAuthenticated,)
    lookup_field = 'project_id'


class GithubHookRequests(APIView):
    permission_classes = (AllowAny,)
    events = {
        'push': event_push,
        'create': event_create,
        'delete': event_delete,
        'issues': event_issue,
    }

    def post(self, request, *args, **kwargs):
        verify, response = verify_secret_hook(request)

        if not verify:
            return response

        event = request.META.get('HTTP_X_GITHUB_EVENT')
        if event == 'ping':
            return HttpResponse(status=200)

        if event in self.events.keys():
            self.events.get(event)(request.data, kwargs.get('project_id'))
            return HttpResponse(status=200)

        return HttpResponse(status=204)
