# -*- coding: utf-8 -*-

from rest_framework import status
from rest_framework.decorators import permission_classes, action
from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound
from applications.api.external.permissions import IsAuthenticatedToken
from .permissions import IsCLI
from .serializers import (
    OrganizationSerializer,
    CreateOrganizationSerializer,
    LicenseInitSerializer,
    LicenseAddSerializer
)
from applications.organization.utils import get_current_organization


class ServerTokenViewSet(ViewSet):
    permission_classes = (IsCLI, )

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        return {
            'request': self.request,
            'format': self.format_kwarg,
            'view': self
        }

    def validate(self, request, *args, **kwargs):
        if request.method == 'POST':
            return self.process_validate(request, request.data, **kwargs)
        elif request.method == 'GET':
            return self.process_validate(request, request.query_params, **kwargs)

    def process_validate(self, request, data, **kwargs):
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)


class UserTokenViewSet(ViewSet):
    permission_classes = (IsAuthenticated, )

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        return {
            'request': self.request,
            'format': self.format_kwarg,
            'view': self
        }

    def validate(self, request, *args, **kwargs):
        if request.method == 'POST':
            return self.process_validate(request, request.data, **kwargs)
        elif request.method == 'GET':
            return self.process_validate(request, request.query_params, **kwargs)

    def process_validate(self, request, data, **kwargs):
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)


class APITokenViewSet(ViewSet):
    permission_classes = (IsAuthenticatedToken, )

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        return {
            'request': self.request,
            'format': self.format_kwarg,
            'view': self
        }

    def validate(self, request, *args, **kwargs):
        if request.method == 'POST':
            return self.process_validate(request, request.data, **kwargs)
        elif request.method == 'GET':
            return self.process_validate(request, request.query_params, **kwargs)

    def process_validate(self, request, data, **kwargs):
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)


class OrganizationViewSet(ViewSet):
    permission_classes = (IsCLI, )
    permission_classes_by_action = {
        'current': [IsCLI | IsAuthenticatedToken],

    }

    def get_permissions(self):
        try:
            # return permission_classes depending on `action`
            if not hasattr(self, 'permission_classes_by_action'):
                raise KeyError
            return [permission() for permission in self.permission_classes_by_action[self.action]]
        except KeyError:
            # action is not set return default permission_classes
            return [permission() for permission in self.permission_classes]

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        return {
            'request': self.request,
            'format': self.format_kwarg,
            'view': self
        }

    def create(self, request, *args, **kwargs):
        serializer_class = CreateOrganizationSerializer
        kwargs['context'] = self.get_serializer_context()
        serializer = serializer_class(data=request.data, **kwargs)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()

    def current(self, request, *args, **kwargs):
        queryset = get_current_organization(request)
        if queryset is None:
            raise NotFound()
        serializer_class = OrganizationSerializer
        kwargs['context'] = self.get_serializer_context()
        serializer = serializer_class(queryset, **kwargs)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LicenseViewSet(ViewSet):
    permission_classes = (IsCLI, )
    permission_classes_by_action = {
        'add': [IsCLI | IsAuthenticatedToken],

    }

    def get_permissions(self):
        try:
            # return permission_classes depending on `action`
            if not hasattr(self, 'permission_classes_by_action'):
                raise KeyError
            return [permission() for permission in self.permission_classes_by_action[self.action]]
        except KeyError:
            # action is not set return default permission_classes
            return [permission() for permission in self.permission_classes]

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        return {
            'request': self.request,
            'format': self.format_kwarg,
            'view': self
        }

    def init(self, request, *args, **kwargs):
        serializer_class = LicenseInitSerializer
        kwargs['context'] = self.get_serializer_context()
        serializer = serializer_class(data=request.data, **kwargs)
        serializer.is_valid(raise_exception=True)
        self.perform_init(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_init(self, serializer):
        serializer.save()

    def add(self, request, *args, **kwargs):
        serializer_class = LicenseAddSerializer
        kwargs['context'] = self.get_serializer_context()
        serializer = serializer_class(data=request.data, **kwargs)
        serializer.is_valid(raise_exception=True)
        self.perform_add(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_add(self, serializer):
        serializer.save()
