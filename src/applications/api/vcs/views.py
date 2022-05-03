# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re

from django.http import Http404
from django.shortcuts import get_object_or_404 as _get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from applications.vcs.tasks import create_area_from_folders_task
from .serializers import *

from .filters import *


def get_object_or_404(queryset, *filter_args, **filter_kwargs):
    """
    Same as Django's standard shortcut, but make sure to also raise 404
    if the filter_kwargs don't match the required types.
    """
    try:
        return _get_object_or_404(queryset, *filter_args, **filter_kwargs)
    except (TypeError, ValueError):
        raise Http404


class AreaModelViewSet(viewsets.ModelViewSet):
    """
    Area API endpoint
    ---
    list:
        List areas endpoint


    create:
        Create area endpoint


    retrieve:
        Retrieve area endpoint


    partial_update:
        Partial update area endpoint


    update:
        Update area endpoint

    create_from_folders:
        Create areas from folders endpoint

    create_links_between_areas:
        Create links between areas(through 'links' field in Area model)

    create_dependencies_between_areas:
        Create dependencies between areas(through 'dependencies' field in Area model)

    search_area_by_name:
        Search area by name in specified project
    """
    model = Area
    queryset = Area.objects.all()
    serializer_class = AreaSerializer
    filter_class = AreaFilterSet

    search_fields = ()
    ordering_fields = ('name', )
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'area_pk'

    def get_queryset(self):
        queryset = super(AreaModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(methods=['POST', ], detail=False, url_path=r'create-from-folders')
    def create_from_folders(self, request, *args, **kwargs):
        """
        Create areas from project folders

        Request should contain next params:
            projectId - id of project which files should be used for creating areas.

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        project_id = request.data.get('project', None)
        project = Project.objects.filter(pk=project_id)
        if not project.exists():
            raise NotFound()

        task = create_area_from_folders_task.delay(project_id)
        return Response(data={'task_id': task.id, 'status': task.status}, status=status.HTTP_200_OK)

    @action(methods=['POST', ], detail=False, url_path=r'linked-areas')
    def create_links_between_areas(self, request, *args, **kwargs):
        """
        Create links between areas(through 'links' field in Area model)

        This function receive POST request that contain data in JSON(see example below) format.
        For each area that contains in 'main_area' key areas from 'linked_areas' will be added
        in 'linked' field.
            After that for each 'main_area' we search all tests that have this area
        in 'area' field. For everyone test we add all linked areas of 'main_area'
        to 'associated_areas' field.

        JSON example:
            [
                {"main_area": 1, "linked_areas": [2]},
                {"main_area": 3, "linked_areas": [1, 2, 4, 5]}
            ]
        :param request:
        :param args:
        :param kwargs:
        :return: HTTP_200_OK or may raise ValidationError
        """
        serializer = AreaLinksSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        for link_case in serializer.validated_data:
            main_area = link_case['main_area']
            areas_to_link = link_case['linked_areas']
            linked_areas_to_remove = main_area.links.exclude(
                id__in=[area.id for area in areas_to_link]
            ).values_list('id', flat=True)
            main_area.links.remove(*linked_areas_to_remove)
            main_area.links.add(*areas_to_link)
            for test in main_area.tests.all():
                test.associated_areas.remove(*linked_areas_to_remove)
                test.associated_areas.add(*areas_to_link)
        return Response(status=status.HTTP_200_OK)

    @action(methods=['POST', ], detail=False, url_path=r'dependent-areas')
    def create_dependencies_between_areas(self, request, *args, **kwargs):
        """
        Create dependencies between areas.

        This function receive POST request that contain data in JSON(see example below) format.
        For each area that contains in 'main_area' key areas from 'dependent_areas' will be added
        in 'dependencies' field.

        JSON example:
            [
                {"main_area": 1, "dependent_areas": [2]},
                {"main_area": 3, "dependent_areas": [1, 2, 4, 5]}
            ]

        :param request:
        :param args:
        :param kwargs:
        :return: HTTP_200_OK or may raise ValidationError
        """
        serializer = AreaDependenciesMakerSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        for link_case in serializer.validated_data:
            main_area = link_case['main_area']
            depended_areas = link_case['dependent_areas']

            depended_areas_to_remove = main_area.dependencies.exclude(
                id__in=[area.id for area in depended_areas]
            ).values_list('id', flat=True)
            main_area.dependencies.remove(*depended_areas_to_remove)
            main_area.dependencies.add(*depended_areas)
        return Response(status=status.HTTP_200_OK)

    @action(methods=['GET', ], detail=False, url_path=r'by-name')
    def search_area_by_name(self, request, *args, **kwargs):
        """
        Search and return area in specified project by name.

        If area isn't be founded then return 'null' in JSON.

        Request should contain next params:
            name - name of searched area.
            project - project id in which to search for an area

        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        area_name = self.request.query_params.get('name', None)
        project_id = self.request.query_params.get('project', None)
        if not area_name:
            return Response(data={'detail': "Argument 'name' isn't provided."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not project_id:
            return Response(data={'detail': "Argument 'project' isn't provided."},
                            status=status.HTTP_400_BAD_REQUEST)
        elif not re.match(r'^\d+$', project_id):
            return Response(data={'detail': "Argument 'project' has wrong format."},
                            status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset().filter(name__exact=area_name, project__exact=project_id)
        if not queryset.exists():
            return Response(data={"area": None}, status=status.HTTP_200_OK)

        if len(queryset) != 1:
            err_info = {
                'project_id': project_id,
                'name': area_name,
                'areas_id': ', '.join([str(area.id) for area in queryset]),
            }
            err_msg = "Found more than one area in project {project_id}" \
                      " with this name '{name}'. Areas id: {areas_id}".format(**err_info)
            return Response(data={'detail': err_msg},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = self.get_serializer(queryset[0], context={'request': request})
        return Response(data={"area": serializer.data}, status=status.HTTP_200_OK)


class BranchModelViewSet(viewsets.ModelViewSet):
    """
    Branch API endpoint
    ---
    list:
        List branches endpoint


    create:
        Create branch endpoint


    retrieve:
        Retrieve branch endpoint


    partial_update:
        Partial update branch endpoint


    update:
        Update branch endpoint


    """
    model = Branch
    serializer_class = BranchSerializer
    queryset = Branch.objects.all()

    filter_class = BranchFilterSet

    search_fields = ()
    ordering_fields = ()
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'branch_pk'

    def get_queryset(self):
        queryset = super(BranchModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset


class CommitModelViewSet(viewsets.ModelViewSet):
    """
    Commit API endpoint
    ---
    list:
        List commits endpoint


    create:
        Create commit endpoint


    retrieve:
        Retrieve commit endpoint


    partial_update:
        Partial update commit endpoint


    update:
        Update commit endpoint


    """
    model = Commit
    serializer_class = CommitSerializer
    queryset = Commit.objects.all()

    filter_class = CommitFilterSet

    search_fields = ()
    ordering_fields = ('timestamp',)
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'commit_pk'

    def get_queryset(self):
        queryset = super(CommitModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.prefetch_related('filechange_set')
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class TagModelViewSet(viewsets.ModelViewSet):
    """
    Tag API endpoint
    ---
    list:
        List tags endpoint


    create:
        Create tag endpoint


    retrieve:
        Retrieve tag endpoint


    partial_update:
        Partial update tag endpoint


    update:
        Update tag endpoint


    """
    model = Tag
    serializer_class = TagSerializer
    queryset = Tag.objects.all()

    filter_class = TagFilterSet

    search_fields = ()
    ordering_fields = ()
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'tag_pk'

    def get_queryset(self):
        queryset = super(TagModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset


class FileModelViewSet(viewsets.ModelViewSet):
    """
    File API endpoint
    ---
    list:
        List files endpoint


    create:
        Create file endpoint


    retrieve:
        Retrieve file endpoint


    partial_update:
        Partial update file endpoint


    update:
        Update file endpoint


    """
    model = File
    serializer_class = FileSerializer
    queryset = File.objects.filter(level=0)
    pagination_class = None

    ordering_fields = ()
    search_fields = ()

    filter_class = FileFilterSet
    filter_fields = ('project', 'area',)

    lookup_field = 'pk'
    lookup_url_kwarg = 'file_pk'

    def get_queryset(self):
        queryset = super(FileModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request))
        return queryset

    def get_serializer(self, *args, **kwargs):
        """
        Return the serializer instance that should be used for validating and
        deserializing input, and for serializing output.
        """
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

    def list(self, request, *args, **kwargs):
        test = request.query_params.get('test')
        type = request.query_params.get('type')

        queryset = self.filter_queryset(self.get_queryset())
        # for item in queryset:
        #     print item

        serializer = self.get_serializer(queryset, context={'test': test, 'type': type}, many=True)
        return Response(serializer.data)

    # def list(self, request, *args, **kwargs):
    #     queryset = self.filter_queryset(self.get_queryset())
    #     serializer = self.get_serializer(queryset, many=True)
    #     return Response(serializer.data)

    @action(methods=['GET'], detail=False, url_path=r'(?P<parent_pk>[0-9]+)/childs')
    def childs(self, request, parent_pk=None):
        test = request.query_params.get('test')
        type = request.query_params.get('type')

        queryset = self.filter_queryset(File.objects.filter(parent=parent_pk))
        serializer = self.get_serializer(queryset, context={'test': test, 'type': type}, many=True)
        return Response(serializer.data)

