from datetime import datetime

from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _
from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from applications.allauth.socialaccount.models import SocialAccount, SocialToken
from applications.api.integration.bitbucket.serializers import BitbucketRepositoryCreateListSerializer
from applications.integration.bitbucket.api import get_full_list_repos, refresh_bitbucket_token
from applications.integration.bitbucket.events import event_push, event_issue
from applications.integration.bitbucket.models import BitbucketRepository
from applications.integration.tasks import clone_repository_task
from applications.organization.utils import get_current_organization


class BitbucketRepositoryCreateListAPIView(ListCreateAPIView):
    """
    Repository API endpoint
    ---
    list:
        List repository endpoint


    create:
        Create repository endpoint


    """
    model = BitbucketRepository
    queryset = BitbucketRepository.objects.all()
    serializer_class = BitbucketRepositoryCreateListSerializer

    permission_classes = (IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)

        # try:
        #     instance.clone_repository()
        #     fetch_commits_task.delay(instance.id, None, BitbucketRepository._meta.model_name)
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
        task = clone_repository_task.delay(instance.id, BitbucketRepository._meta.model_name)
        return Response(data={'task_id': task.id, 'status': task.status}, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        organization = get_current_organization(self.request)
        user = self.request.user
        assert organization.is_member(user) is True
        social_token = SocialAccount.objects.filter(user=user,
                                                    provider='bitbucket_oauth2').first().socialtoken_set.first()
        instance = serializer.save(user=user, social_token=social_token)
        return instance


class BitbucketHookRequests(APIView):
    permission_classes = (AllowAny,)
    events = {
        'push': event_push,
        'issue': event_issue,
    }

    def post(self, request, *args, **kwargs):
        request_keys = request.data.keys()
        project_id = kwargs.get('project_id')

        if 'push' in request_keys:
            event_push(data=request.data, project_id=project_id)

        if 'issue' in request_keys:
            event_issue(data=request.data, project_id=project_id)

        return HttpResponse(status=200)


class BitbucketRepositoryFullListAPIView(APIView):
    """
    Repository list from Bitbucket endpoint
    ---
    list:
        List repository from bitbucket endpoint


    """

    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        try:
            social_token = SocialToken.objects.get(account__id=request.query_params.get('id', None),
                                                   app__provider='bitbucket_oauth2')
        except SocialToken.DoesNotExist:
            return Response({'detail': [_('Access token does not exists')]},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        expire = social_token.expires_at.replace(tzinfo=None)
        access_token = social_token.token

        if datetime.now() > expire:
            json_response = refresh_bitbucket_token(social_token=social_token)

            if json_response:
                access_token = json_response.get('access_token')

        repos = get_full_list_repos(access_token)

        return Response({'repos': repos}, status=status.HTTP_200_OK)
