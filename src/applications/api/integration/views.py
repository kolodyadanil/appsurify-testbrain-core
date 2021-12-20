# -*- coding: utf-8 -*-

import base64

from django.contrib.auth import get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpResponse
from django.template.defaultfilters import slugify

from rest_framework.decorators import action
from rest_framework import status, permissions, views, viewsets, generics, response, exceptions

from applications.api.external.utils import ConfirmationHMAC
from applications.allauth.socialaccount.models import SocialToken, SocialAccount
from applications.integration.tasks import make_clone_workflow, make_processing_workflow

from applications.organization.utils import get_current_organization
from applications.project.models import Project

from applications.integration.github.models import GithubRepository
from applications.integration.bitbucket.models import BitbucketRepository
from applications.integration.perforce.models import PerforceRepository
from applications.integration.git.models import GitRepository
from applications.integration.ssh.models import GitSSHRepository
from applications.integration.ssh_v2.models import GitSSHv2Repository

from .serializers import (
    GithubRepositoryCreateListSerializer,
    BitbucketRepositoryCreateListSerializer,
    PerforceRepositoryCreateListSerializer,
    GitRepositoryCreateListSerializer,
    GitSSHRepositoryCreateListSerializer,
    GitSSHv2RepositoryCreateListSerializer,

)


User = get_user_model()


class RepositoryInterface(object):
    model = None
    serializer_class = None
    format_kwarg = None

    def __init__(self, *args, **kwargs):
        self.context = kwargs['context']
        self.request = self.context['request']

    def get_serializer(self, *args, **kwargs):
        """
        Return the serializer instance that should be used for validating and
        deserializing input, and for serializing output.
        """
        serializer_class = self.get_serializer_class()
        kwargs['context'] = self.get_serializer_context()
        return serializer_class(*args, **kwargs)

    def get_serializer_class(self):
        """
        Return the class to use for the serializer.
        Defaults to using `self.serializer_class`.

        You may want to override this if you need to provide different
        serializations depending on the incoming request.

        (Eg. admins get full serialization, others get basic serialization)
        """
        assert self.serializer_class is not None, (
            "'%s' should either include a `serializer_class` attribute, "
            "or override the `get_serializer_class()` method."
            % self.__class__.__name__
        )

        return self.serializer_class

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        return {
            'request': self.request,
            'format': self.format_kwarg,
            'view': self
        }

    def list(self, *args, **kwargs):
        raise NotImplementedError('Do not implemented or not supported.')

    def create(self, *args, **kwargs):
        raise NotImplementedError('Do not implemented or not supported.')

    def retrieve(self, *args, **kwargs):
        raise NotImplementedError('Do not implemented or not supported.')

    def destroy(self, *args, **kwargs):
        raise NotImplementedError('Do not implemented or not supported.')

    def full(self, *args, **kwargs):
        raise NotImplementedError('Do not implemented or not supported.')

    def connect(self, *args, **kwargs):
        raise NotImplementedError('Do not implemented or not supported.')

    def hook_receive(self, project_id, repository_id, *args, **kwargs):
        raise NotImplementedError('Do not implemented or not supported.')

    def hook_verify_request(self):
        # TODO: Maybe set default allow or deny
        raise NotImplementedError('Do not implemented or not supported.')

    def hook_install(self, project_id, repository_id, *args, **kwargs):
        raise NotImplementedError('Do not implemented or not supported.')

    def hook_generate(self, project_id, repository_id, *args, **kwargs):
        raise NotImplementedError('Do not implemented or not supported.')

    def run_clone_workflow(self, repository):
        workflow = make_clone_workflow(
            project_id=repository.project_id,
            repository_id=repository.id,
            model_name=repository._meta.model_name
        )
        task = workflow.delay()
        return task

    def run_push_workflow(self, repository, data, since_time=None):
        workflow = make_processing_workflow(
            project_id=repository.project_id,
            repository_id=repository.id,
            model_name=repository._meta.model_name, data=data, since_time=since_time
        )
        task = workflow.delay()
        return task


class GitHubRepositoryWrapper(RepositoryInterface):

    model = GithubRepository
    serializer_class = GithubRepositoryCreateListSerializer

    def create(self, *args, **kwargs):
        organization = get_current_organization(self.request)
        user = self.request.user
        is_member = organization.is_member(user)
        if not is_member:
            raise exceptions.PermissionDenied('You have no permissions.')
        social_token = SocialAccount.objects.filter(provider='github',
                                                    user=user).first().socialtoken_set.first().token

        serializer = self.get_serializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        repository = serializer.save(user=user, token=social_token)
        task = self.run_clone_workflow(repository=repository)
        return {'task_id': task.id, 'status': task.status}

    def retrieve(self, pk, *args, **kwargs):
        repository_instance = self.model.objects.get(project_id=pk)
        serializer = self.get_serializer(repository_instance)
        return serializer.data

    def destroy(self, pk, *args, **kwargs):
        repository_instance = self.model.objects.get(project_id=pk)
        repository_instance.delete()
        return {}

    def full(self, *args, **kwargs):
        token_obj = SocialToken.objects.get(account__id=self.request.query_params.get('id', None),
                                            app__provider='github')
        list_repos = self.model.get_full_list_repos(token_obj)
        return {'repos': list_repos}

    def hook_verify_request(self):
        from applications.integration.github.utils import verify_secret_hook
        verify, message = verify_secret_hook(request=self.request, context=self.context)
        if not verify:
            raise exceptions.PermissionDenied('Permission denied. Secret not verified.')
        return verify, message

    def hook_receive(self, project_id, repository_id, *args, **kwargs):

        self.hook_verify_request()

        params = {'project_id': project_id}

        if repository_id is not None:
            params['id'] = repository_id

        repository = self.model.objects.get(**params)

        status, message = repository.receive_webhook(request=self.request, context=self.context)
        return {'status': status, 'message': message}


class BitBucketRepositoryWrapper(RepositoryInterface):

    model = BitbucketRepository
    serializer_class = BitbucketRepositoryCreateListSerializer

    def create(self, *args, **kwargs):
        organization = get_current_organization(self.request)
        user = self.request.user

        is_member = organization.is_member(user)

        if not is_member:
            raise exceptions.PermissionDenied('You have no permissions.')

        social_token = SocialAccount.objects.filter(
            provider='bitbucket_oauth2', user=user).first().socialtoken_set.first()

        serializer = self.get_serializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        repository = serializer.save(user=user, social_token=social_token)
        task = self.run_clone_workflow(repository=repository)
        return {'task_id': task.id, 'status': task.status}

    def retrieve(self, pk, *args, **kwargs):
        repository_instance = self.model.objects.get(project_id=pk)
        serializer = self.get_serializer(repository_instance)
        return serializer.data

    def destroy(self, pk, *args, **kwargs):
        repository_instance = self.model.objects.get(project_id=pk)
        repository_instance.delete()
        return {}

    def full(self, *args, **kwargs):
        token_obj = SocialToken.objects.get(account__id=self.request.query_params.get('id', None),
                                            app__provider='bitbucket_oauth2')
        list_repos = self.model.get_full_list_repos(token_obj)
        return {'repos': list_repos}

    def hook_verify_request(self):
        pass

    def hook_receive(self, project_id, repository_id, *args, **kwargs):

        self.hook_verify_request()

        params = {'project_id': project_id}

        if repository_id is not None:
            params['id'] = repository_id

        repository_instance = self.model.objects.get(**params)
        status, message = repository_instance.receive_webhook(request=self.request, context=self.context)
        return {'status': status, 'message': message}


class PerforceRepositoryWrapper(RepositoryInterface):

    model = PerforceRepository
    serializer_class = PerforceRepositoryCreateListSerializer

    def create(self, *args, **kwargs):
        organization = get_current_organization(self.request)
        user = self.request.user

        is_member = organization.is_member(user)

        if not is_member:
            raise exceptions.PermissionDenied('You have no permissions.')

        serializer = self.get_serializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)

        repository = serializer.save(user=user)
        # task = self.run_clone_workflow(repository=repository)
        # return {'task_id': task.id, 'status': task.status}
        return {'task_id': 'unknown', 'status': 'SUCCESS'}

    def hook_receive(self, project_id, repository_id, *args, **kwargs):
        params = {'project_id': project_id}
        if repository_id is not None:
            params['id'] = repository_id

        repository_instance = self.model.objects.get(**params)
        status, message = repository_instance.receive_webhook(request=self.request, context=self.context)
        return {'status': status, 'message': message}


class GitRepositoryWrapper(RepositoryInterface):

    model = GitRepository
    serializer_class = GitRepositoryCreateListSerializer

    def create(self, *args, **kwargs):
        organization = get_current_organization(self.request)
        user = self.request.user

        is_member = organization.is_member(user)

        if not is_member:
            raise exceptions.PermissionDenied('You have no permissions.')

        serializer = self.get_serializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)

        project = serializer.validated_data['project']
        host = serializer.validated_data['host']
        port = 22
        if host.find(':') >= 0:
            host, port = host.split(':')
        else:
            host, port = host, 22

        git_repository_name = '{}/{}'.format(user.username, project.slug)

        repository = serializer.save(user=user, git_repository_name=git_repository_name, host=host, port=port)
        task = self.run_clone_workflow(repository=repository)
        return {'task_id': task.id, 'status': task.status}

    def connect(self, *args, **kwargs):
        data = self.request.data

        host = data.get('host')
        port = data.get('port', 22)
        username = data.get('login')
        password = data.get('password')

        if host.find(':') >= 0:
            host, port = host.split(':')

        status, message = self.model.test_connection(host, port, username, password)
        return {'status': status, 'message': message, 'detail': [message,]}

    def hook_verify_request(self):
        pass

    def hook_receive(self, project_id, repository_id, *args, **kwargs):

        self.hook_verify_request()

        params = {'project_id': project_id}

        if repository_id is not None:
            params['id'] = repository_id

        repository_instance = self.model.objects.get(**params)
        status, message = repository_instance.receive_webhook(request=self.request, context=self.context)
        return {'status': status, 'message': message}

    def hook_install(self, project_id, repository_id, *args, **kwargs):
        params = {'project_id': project_id}
        if repository_id is not None:
            params['id'] = repository_id

        repository_instance = self.model.objects.get(**params)
        status, message = repository_instance.install_webhook(request=self.request, context=self.context)
        return {'status': status, 'message': message}

    def hook_generate(self, project_id, repository_id, *args, **kwargs):
        params = {'project_id': project_id}
        if repository_id is not None:
            params['id'] = repository_id

        repository_instance = self.model.objects.get(**params)
        data = repository_instance.generate_webhook(request=self.request, context=self.context)
        return {'content_type': 'text/plain', 'content': data, 'filename': 'hook.py'}


class GitSSHRepositoryWrapper(RepositoryInterface):

    model = GitSSHRepository
    serializer_class = GitSSHRepositoryCreateListSerializer

    def create(self, *args, **kwargs):
        organization = get_current_organization(self.request)
        user = self.request.user

        is_member = organization.is_member(user)

        if not is_member:
            raise exceptions.PermissionDenied('You have no permissions.')

        data = self.request.data.copy()

        private_key_file = self.request.FILES.get('private_key')
        if private_key_file is None:
            private_key_file = data['private_key']

        private_key_raw = private_key_file.file.read()
        private_key = base64.encodestring(private_key_raw)
        data['private_key'] = private_key

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        repository = serializer.save()
        # task = self.run_clone_workflow(repository=repository)
        # return {'task_id': task.id, 'status': task.status}
        return {'task_id': 'unknown', 'status': 'SUCCESS'}

    def hook_receive(self, project_id, repository_id, *args, **kwargs):
        params = {'project_id': project_id}
        if repository_id is not None:
            params['id'] = repository_id

        repository_instance = self.model.objects.get(**params)
        status, message = repository_instance.receive_webhook(request=self.request, context=self.context)
        return {'status': status, 'message': message}


class GitSSHv2RepositoryWrapper(RepositoryInterface):

    model = GitSSHv2Repository
    serializer_class = GitSSHv2RepositoryCreateListSerializer

    def create(self, *args, **kwargs):
        organization = get_current_organization(self.request)
        user = self.request.user

        is_member = organization.is_member(user)

        if not is_member:
            raise exceptions.PermissionDenied('You have no permissions.')

        data = self.request.data.copy()

        project = Project.objects.get(id=data.get('project'))
        repository_name = slugify(project.name)

        data['user'] = user.pk
        data['project'] = project.pk
        data['repository_name'] = repository_name

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        repository = serializer.save()
        # task = self.run_clone_workflow(repository=repository)
        # return {'task_id': task.id, 'status': task.status}
        return {'task_id': 'unknown', 'status': 'SUCCESS'}

    def retrieve(self, pk, *args, **kwargs):
        repository_instance = self.model.objects.get(pk=pk)
        serializer = self.get_serializer(repository_instance)
        return serializer.data

    def destroy(self, pk, *args, **kwargs):
        repository_instance = self.model.objects.get(pk=pk)
        repository_instance.delete()
        return {}

    def hook_receive(self, project_id, repository_id, *args, **kwargs):
        params = {'project_id': project_id}
        if repository_id is not None:
            params['id'] = repository_id

        token = self.request.META.get('HTTP_TOKEN', '')
        organization_from_token = ConfirmationHMAC.from_key(token)
        organization = get_current_organization(self.request)
        if organization != organization_from_token:
            raise exceptions.AuthenticationFailed()

        repository_instance = self.model.objects.get(**params)
        status, message = repository_instance.receive_webhook(request=self.request, context=self.context)
        return {'status': status, 'message': message}

    def hook_generate(self, project_id, repository_id, *args, **kwargs):
        params = {'project_id': project_id}
        if repository_id is not None:
            params['id'] = repository_id

        repository_instance = self.model.objects.get(**params)
        data = repository_instance.generate_webhook(request=self.request, context=self.context)
        return {'content_type': 'application/octet-stream', 'content': data, 'filename': 'install.py'}


class RepositoryGenericViewSet(viewsets.GenericViewSet):

    def initialize_request(self, request, *args, **kwargs):
        self.repository_type = kwargs.pop('type')
        setattr(request, 'raw_body', request.body)
        return super(RepositoryGenericViewSet, self).initialize_request(request, *args, **kwargs)

    def get_repository_class(self):
        return self.repository_classes[self.repository_type]

    def get_repository_context(self):
        body = self.request.raw_body
        return {
            'request': self.request,
            'query_params': self.request.query_params,
            'data': self.request.data,
            'body': body,
            'view': self
        }

    def get_repository(self, *args, **kwargs):
        repository_class = self.get_repository_class()
        kwargs['context'] = self.get_repository_context()
        return repository_class(*args, **kwargs)


class RepositoryViewSet(RepositoryGenericViewSet):
    # permission_classes = [permissions.AllowAny, ]

    repository_classes = {
        'github': GitHubRepositoryWrapper,
        'bitbucket': BitBucketRepositoryWrapper,
        'perforce': PerforceRepositoryWrapper,
        'git': GitRepositoryWrapper,
        'ssh': GitSSHRepositoryWrapper,
        'ssh_v2': GitSSHv2RepositoryWrapper,

    }

    def create(self, request, *args, **kwargs):
        repository = self.get_repository(*args, **kwargs)
        data = repository.create(*args, **kwargs)
        return response.Response(status=status.HTTP_200_OK, data=data)

    def retrieve(self, request, pk, *args, **kwargs):
        repository = self.get_repository(*args, **kwargs)
        data = repository.retrieve(pk, *args, **kwargs)
        return response.Response(status=status.HTTP_200_OK, data=data)

    def destroy(self, request, pk, *args, **kwargs):
        repository = self.get_repository(*args, **kwargs)
        data = repository.destroy(pk, *args, **kwargs)
        return response.Response(status=status.HTTP_204_NO_CONTENT, data=data)

    @action(methods=['GET', ], detail=False, url_name='full-list', url_path=r'full')
    def full(self, request, *args, **kwargs):
        repository = self.get_repository(*args, **kwargs)
        data = repository.full()
        return response.Response(status=status.HTTP_200_OK, data=data)

    @action(methods=['POST', ], detail=False, url_name='test', url_path=r'connect')
    def connect(self, request, *args, **kwargs):
        repository = self.get_repository(*args, **kwargs)
        data = repository.connect(*args, **kwargs)
        if data['status'] is False:
            return response.Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, data=data)
        return response.Response(status=status.HTTP_200_OK, data=data)


class RepositoryHookViewSet(RepositoryGenericViewSet):
    # permission_classes = [permissions.AllowAny, ]

    repository_classes = {
        'github': GitHubRepositoryWrapper,
        'bitbucket': BitBucketRepositoryWrapper,
        'perforce': PerforceRepositoryWrapper,
        'git': GitRepositoryWrapper,
        'ssh': GitSSHRepositoryWrapper,
        'ssh_v2': GitSSHv2RepositoryWrapper,

    }

    @action(methods=['POST', ], detail=False, permission_classes=[permissions.AllowAny,],
            url_name='receive', url_path=r'(?P<project_id>[0-9]+)(/(?P<repository_id>[0-9]+))?')
    def receive(self, request, project_id, repository_id, *args, **kwargs):
        repository = self.get_repository(*args, **kwargs)
        project = Project.objects.get(id=project_id)
        if not project.is_active:
            return response.Response(
                data={"detail": "Project is not active"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        data = repository.hook_receive(project_id, repository_id, *args, **kwargs)
        if data['status'] is False:
            return response.Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, data=data)
        return response.Response(status=status.HTTP_200_OK, data=data)

    @action(methods=['POST', ], detail=False, url_name='install',
            url_path=r'(?P<project_id>[0-9]+)(/(?P<repository_id>[0-9]+))?/install')
    def install(self, request, project_id, repository_id, *args, **kwargs):
        repository = self.get_repository(*args, **kwargs)
        data = repository.hook_install(project_id, repository_id, *args, **kwargs)
        return response.Response(status=status.HTTP_200_OK, data=data)

    @action(methods=['GET', 'POST', ], detail=False, url_name='generate',
            url_path=r'(?P<project_id>[0-9]+)(/(?P<repository_id>[0-9]+))?/generate')
    def generate(self, request, project_id, repository_id, *args, **kwargs):
        repository = self.get_repository(*args, **kwargs)
        data = repository.hook_generate(project_id, repository_id, *args, **kwargs)
        # return response.Response(status=status.HTTP_200_OK, data=data['data'], content_type=data['content_type'])
        response = HttpResponse(status=status.HTTP_200_OK, content_type=data['content_type'])
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(data['filename'])
        response.write(data['content'])
        return response
