# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime

import pytz
from django.http import Http404
from django.shortcuts import get_object_or_404 as _get_object_or_404
from django.utils.text import slugify
from rest_framework import permissions
from rest_framework import viewsets, status
from rest_framework.response import Response

from applications.notification.models import Notification
from applications.organization.utils import get_current_organization
from applications.project.permissions import IsOwnerOrReadOnly, IsAdminOrganizationOrReadOnly
from .filters import *
from .serializers import *

UserModel = get_user_model()


def get_object_or_404(queryset, *filter_args, **filter_kwargs):
    """
    Same as Django's standard shortcut, but make sure to also raise 404
    if the filter_kwargs don't match the required types.
    """
    try:
        return _get_object_or_404(queryset, *filter_args, **filter_kwargs)
    except (TypeError, ValueError):
        raise Http404


class ProjectModelViewSet(viewsets.ModelViewSet):
    """
    Project API endpoints
    ---
    list:
        List projects endpoint.
        Projects, only those that make up the current user.


    create:
        Create project endpoint.
            - name: string
            - organization: automate detection field


    retrieve:
        Retrieve project endpoint.


    partial_update:
        Partial update project endpoint.


    update:
        Update project endpoint.


    change_owner:
        Change owner project.
            - project_pk: int
            - data (user_id): {"id": int}


    """
    model = Project

    serializer_class = ProjectSerializer

    filter_class = ProjectFilterSet
    queryset = Project.objects.all()

    permission_classes = (permissions.IsAuthenticated, IsAdminOrganizationOrReadOnly or IsOwnerOrReadOnly,)
    ordering_fields = ()
    search_fields = ()
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'project_pk'

    def get_queryset(self):
        queryset = super(ProjectModelViewSet, self).get_queryset()
        user = self.request.user
        if user.is_superuser:
            return queryset

        organization = get_current_organization(request=self.request)
        if organization:
            queryset = queryset.filter(organization=organization)
            if not organization.is_admin(user):
                queryset = queryset.get_for_user(user)

        return queryset

    def create(self, request, *args, **kwargs):
        project_data = request.data.copy()

        organization = get_current_organization(request=request)

        project_data.update(dict(organization=organization.id))
        project_data.update(dict(slug=slugify(project_data['name'])))

        serializer = self.get_serializer(data=project_data)

        serializer.is_valid(raise_exception=True)

        project = self.perform_create(serializer)

        serializer.instance.add_user(request.user)

        Notification.objects.create(project=serializer.instance, type=Notification.TYPE_RISK,
                                    period=Notification.PERIOD_WEEKLY, schedule_hour=0,
                                    schedule_weekday=7, schedule_timezone='US/Pacific',
                                    emails=serializer.instance.owner.project_user.user.email,
                                    schedule_last_send=datetime.datetime.now().replace(tzinfo=pytz.timezone('UTC')))

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def change_owner(self, request, *args, **kwargs):
        project = self.get_object()
        organization = project.organization
        user_id = request.data.get('id')
        user = UserModel.objects.get(id=user_id)

        if organization.is_member(user=user):
            project_user = project.project_users.get(user_id=user_id)
            project_owner = project.change_owner(new_owner=project_user)
        else:
            raise Exception('User not member of organization')

        serializer = self.get_serializer(project_owner)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_200_OK, headers=headers)


class ProjectUserModelViewSet(viewsets.ModelViewSet):
    """
    Project User API endpoint.
    ---
    list:
        List project user endpoint.


    create:
        Create project user endpoint.
        Add user to project members.


    destroy:
        Destroy project user endpoint.
        Delete user from project members.


    """
    model = ProjectUser
    serializer_class = ProjectUserSerializer
    queryset = ProjectUser.objects.all()

    permission_classes = (permissions.IsAuthenticated, IsOwnerOrReadOnly,)
    ordering_fields = '__all__'
    search_fields = ()
    # filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'project_user_pk'

    lookup_project_field = 'pk'
    lookup_project_url_kwarg = 'project_pk'

    def get_project(self):
        """
        Returns the object the view is displaying.

        You may want to override this if you need to provide non-standard
        queryset lookups.  Eg if objects are referenced using multiple
        keyword arguments in the url conf.
        """

        try:

            queryset = Project.objects.all()

            # Perform the lookup filtering.
            lookup_project_url_kwarg = self.lookup_project_url_kwarg or self.lookup_project_field

            assert lookup_project_url_kwarg in self.kwargs, (
                    'Expected view %s to be called with a URL keyword argument '
                    'named "%s". Fix your URL conf, or set the `.lookup_field` '
                    'attribute on the view correctly.' %
                    (self.__class__.__name__, lookup_project_url_kwarg)
            )

            filter_kwargs = {self.lookup_project_field: self.kwargs[lookup_project_url_kwarg]}
            obj = get_object_or_404(queryset, **filter_kwargs)

            # May raise a permission denied
            self.check_object_permissions(self.request, obj)
            return obj

        except AssertionError:
            return None

    def get_queryset(self):
        queryset = super(ProjectUserModelViewSet, self).get_queryset()
        user = self.request.user

        if user.is_superuser:
            return queryset

        if self.get_project():
            queryset = queryset.filter(project=self.get_project())

        return queryset

    def create(self, request, *args, **kwargs):
        project = self.get_project()
        organization = project.organization
        user_id = request.data.get('id')
        user = UserModel.objects.get(id=user_id)

        if organization.is_member(user=user):
            project_user, _ = project.get_or_add_user(user=user)
        else:
            raise Exception()

        serializer = self.get_serializer(project_user)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        project = self.get_project()
        organization = project.organization
        user_id = kwargs.get('project_user_pk')
        user = UserModel.objects.get(id=user_id)

        if organization.is_member(user=user):
            project.remove_user(user=user)
        else:
            raise Exception()

        return Response({}, status=status.HTTP_200_OK)
