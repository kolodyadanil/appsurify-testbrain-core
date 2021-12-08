# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import copy
import inspect
import traceback

from django.db import transaction
from collections import OrderedDict
from django.db.models import Q

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from rest_framework.serializers import raise_errors_on_nested_writes
from rest_framework.utils import html, model_meta

from rest_framework_recursive.fields import RecursiveField
from generic_relations.relations import GenericRelatedField

from applications.api.common.serializers import DynamicFieldsModelSerializer, DynamicFieldsRelatedSerializer, \
    FlexFieldsSerializerMixin
from applications.organization.utils import get_current_organization
from applications.project.models import Project
from applications.testing.models import Test
from applications.vcs.models import *
from applications.api.project.serializers import ProjectRelatedSerializer


class FileSerializer(DynamicFieldsModelSerializer):
    has_childs = serializers.SerializerMethodField()
    child_cnt = serializers.SerializerMethodField()
    is_associated = serializers.SerializerMethodField()

    # rank = serializers.SerializerMethodField()

    class Meta(object):
        model = File
        # fields = ('id', 'filename', 'has_childs')
        fields = '__all__'

    def get_has_childs(self, obj):
        if obj.get_descendant_count() > 0:
            return True
        return False

    def get_child_cnt(self, obj):
        if obj.get_descendant_count() > 0:
            return obj.get_descendant_count()
        return 0

    def get_is_associated(self, obj):
        result = 0
        is_associated = getattr(obj, 'is_associated', False)
        area = getattr(obj, 'is_area', None)
        test = self.context.get('test')
        type = self.context.get('type')

        if type:
            tt = Test.objects.filter(pk=test)[0]
            _count = obj.get_descendants().filter(~Q(sha='')).count()

            words = tt.name.split(' ')
            tfiles = []
            for word in words:
                tfiles += File.objects.filter(Q(filename__contains=word) & Q(project=tt.project) & ~Q(sha='')).values('id', 'filename', 'full_filename')

            tfileIds = []
            for tfile in tfiles:
                tfileIds.append(tfile['id'])

            _associated_count = obj.get_descendants().filter(id__in=tfileIds).count()
            #_associated_count = len(tfiles)

            if _count > 0 and _associated_count > 0:
                if _count == _associated_count:
                    result = 1
                elif _count > _associated_count:
                    result = 2
            elif _associated_count == 0 and _count == 0:
                if getattr(obj, 'id') in tfileIds:
                    result = 1

        elif test:
            tt = Test.objects.filter(pk=test)[0]
            _count = obj.get_descendant_count()
            if _count > 0:
                _associated_count = obj.get_descendants().filter(associated_files__id=test).count()
            else:
                _associated_count = 0
                _associated_files = list(getattr(tt, 'associated_files').values('id'))
                _associated_file_ids = []
                for _associated_file in _associated_files:
                    _associated_file_ids.append(_associated_file['id'])

                if getattr(obj, 'id') in _associated_file_ids:
                    _associated_count = 1
                else:
                    _associated_count = 0

            if _count > 0 and _associated_count > 0:
                if _count == _associated_count:
                    result = 1
                elif _count > _associated_count:
                    result = 2
            elif _count == 0 and _associated_count > 0:
                result = 1
            elif _associated_count == 0 and _count == 0:
                if is_associated:
                    result = 1

        elif area:
            _count = obj.get_descendant_count()
            _associated_count = obj.get_descendants().filter(areas__id=area).count()
            if _count > 0 and _associated_count > 0:
                if _count == _associated_count:
                    result = 1
                elif _count > _associated_count:
                    result = 2
            elif _associated_count == 0 and _count == 0:
                if is_associated:
                    result = 1

        return result


class FileRelatedSerializer(DynamicFieldsRelatedSerializer):

    class Meta(object):
        model_class = File
        model_serializer_class = FileSerializer


class FileChangeSerializer(DynamicFieldsModelSerializer):
    id = serializers.ReadOnlyField(source='project_file.id')
    filename = serializers.ReadOnlyField(source='project_file.filename')

    class Meta(object):
        model = FileChange
        fields = ('id', 'filename', 'patch', 'status',)


class AreaDependenciesSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=False, required=True)
    project = ProjectRelatedSerializer(fields=('id', 'name'), queryset=Project.objects.all())
    name = serializers.CharField()


class AreaSerializer(FlexFieldsSerializerMixin, serializers.ModelSerializer):
    project = ProjectRelatedSerializer(fields=('id', 'name'), queryset=Project.objects.all())
    files = serializers.ManyRelatedField(child_relation=serializers.PrimaryKeyRelatedField(queryset=File.objects.all()),
                                         required=False)

    class Meta(object):
        model = Area
        fields = '__all__'

    expandable_fields = {'dependencies': (AreaDependenciesSerializer, {'source': 'dependencies', 'many': True})}

    @transaction.atomic
    def update(self, instance, validated_data):
        raise_errors_on_nested_writes('update', self, validated_data)
        info = model_meta.get_field_info(instance)

        # Simply set each attribute on the instance, and then save it.
        # Note that unlike `.create()` we don't need to treat many-to-many
        # relationships as being a special case. During updates we already
        # have an instance pk for the relationships to be associated with.
        for attr, value in validated_data.items():
            if attr in info.relations and info.relations[attr].to_many:
                field = getattr(instance, attr)
                field.set(value)
            else:
                setattr(instance, attr, value)

        if 'files' in self.initial_data:
            files = self.initial_data.get('files')

            file_list = list()
            for file in files:
                if isinstance(file, dict):
                    file_id = file.get('id')
                elif isinstance(file, int):
                    file_id = file
                else:
                    continue

                file_list.append(file_id)

            instance.files.clear()

            trees = list()

            _root_nodes = File.objects.order_by('tree_id').filter(id__in=file_list, level=0).exists()
            if _root_nodes:
                _files = File.objects.filter(id__in=file_list).order_by('tree_id')
                for file_instance in _files:
                    _is_root = file_instance.is_root_node()
                    _is_child = file_instance.is_child_node()
                    _is_leaf = file_instance.is_leaf_node()

                    # PREPARE ROOT NODES
                    if _is_root:
                        _children_count = file_instance.get_children().filter(id__in=file_list).count()
                        if _children_count > 0:
                            trees.append(file_instance)
                            _children_files = file_instance.get_children().filter(id__in=file_list).iterator()
                            trees.extend(_children_files)
                        elif file_instance.get_children().filter(id__in=file_list).count() == 0:
                            trees.append(file_instance)
                            _children_files = file_instance.get_descendants(include_self=False).iterator()
                            trees.extend(_children_files)
                        else:
                            pass

                    # PREPARE MIDDLE NODES
                    elif _is_child and not _is_leaf:
                        if file_instance.id in file_list:
                            if file_instance.parent_id in file_list:
                                if file_instance.get_children().filter(id__in=file_list).count() > 0:
                                    trees.append(file_instance)
                                    _children_files = file_instance.get_children().filter(id__in=file_list).iterator()
                                    trees.extend(_children_files)
                                elif file_instance.get_children().filter(id__in=file_list).count() == 0:
                                    trees.append(file_instance)
                                    _children_files = file_instance.get_descendants(include_self=False).iterator()
                                    trees.extend(_children_files)
                                else:
                                    pass

                    # PREPARE LEAF NODE
                    elif file_instance.is_leaf_node():
                        if file_instance.parent_id in file_list:
                            trees.append(file_instance)

            instance.files.add(*trees)

        instance.save()
        return instance

    @transaction.atomic
    def create(self, validated_data):
        raise_errors_on_nested_writes('create', self, validated_data)
        ModelClass = self.Meta.model

        # Remove many-to-many relationships from validated_data.
        # They are not valid arguments to the default `.create()` method,
        # as they require that the instance has already been saved.
        info = model_meta.get_field_info(ModelClass)
        many_to_many = {}
        for field_name, relation_info in info.relations.items():
            if relation_info.to_many and (field_name in validated_data):
                many_to_many[field_name] = validated_data.pop(field_name)

        try:
            instance = ModelClass.objects.create(**validated_data)
        except TypeError:
            tb = traceback.format_exc()
            msg = (
                'Got a `TypeError` when calling `%s.objects.create()`. '
                'This may be because you have a writable field on the '
                'serializer class that is not a valid argument to '
                '`%s.objects.create()`. You may need to make the field '
                'read-only, or override the %s.create() method to handle '
                'this correctly.\nOriginal exception was:\n %s' %
                (
                    ModelClass.__name__,
                    ModelClass.__name__,
                    self.__class__.__name__,
                    tb
                )
            )
            raise TypeError(msg)

        # Save many-to-many relationships after the instance is created.
        if many_to_many:
            for field_name, value in many_to_many.items():
                field = getattr(instance, field_name)
                field.set(value)

        if 'files' in self.initial_data:
            files = self.initial_data.get('files')

            file_list = list()
            for file in files:
                if isinstance(file, dict):
                    file_id = file.get('id')
                elif isinstance(file, int):
                    file_id = file
                else:
                    continue

                file_list.append(file_id)

            instance.files.clear()

            trees = list()

            _root_nodes = File.objects.order_by('tree_id').filter(id__in=file_list, level=0).exists()
            if _root_nodes:
                _files = File.objects.filter(id__in=file_list).order_by('tree_id')
                for file_instance in _files:
                    _is_root = file_instance.is_root_node()
                    _is_child = file_instance.is_child_node()
                    _is_leaf = file_instance.is_leaf_node()

                    # PREPARE ROOT NODES
                    if _is_root:
                        _children_count = file_instance.get_children().filter(id__in=file_list).count()
                        if _children_count > 0:
                            trees.append(file_instance)
                            _children_files = file_instance.get_children().filter(id__in=file_list).iterator()
                            trees.extend(_children_files)
                        elif file_instance.get_children().filter(id__in=file_list).count() == 0:
                            trees.append(file_instance)
                            _children_files = file_instance.get_descendants(include_self=False).iterator()
                            trees.extend(_children_files)
                        else:
                            pass

                    # PREPARE MIDDLE NODES
                    elif _is_child and not _is_leaf:
                        if file_instance.id in file_list:
                            if file_instance.parent_id in file_list:
                                if file_instance.get_children().filter(id__in=file_list).count() > 0:
                                    trees.append(file_instance)
                                    _children_files = file_instance.get_children().filter(id__in=file_list).iterator()
                                    trees.extend(_children_files)
                                elif file_instance.get_children().filter(id__in=file_list).count() == 0:
                                    trees.append(file_instance)
                                    _children_files = file_instance.get_descendants(include_self=False).iterator()
                                    trees.extend(_children_files)
                                else:
                                    pass

                    # PREPARE LEAF NODE
                    elif file_instance.is_leaf_node():
                        if file_instance.parent_id in file_list:
                            trees.append(file_instance)

            instance.files.add(*trees)

        instance.save()
        return instance


class AreaFromProjectSerializer(DynamicFieldsModelSerializer):
    class Meta(object):
        model = Area
        fields = ('id',)

    def save(self, request):
        cls = self.Meta.model

        project_id = request.data['projectId']
        file_list = File.objects.filter(project=project_id).values_list('id', flat=True)

        _root_nodes = File.objects.order_by('tree_id').filter(id__in=file_list, level=0).exists()
        if _root_nodes:
            _files = File.objects.filter(id__in=file_list).order_by('tree_id')
            for file_instance in _files:
                _is_root = file_instance.is_root_node()
                _is_child = file_instance.is_child_node()
                _is_leaf = file_instance.is_leaf_node()

                if not _is_leaf:
                    _children_files = file_instance.get_children().filter(id__in=file_list).iterator()
                    _is_folder = False
                    area_files = list()
                    for _child_file in _children_files:
                        if _child_file.is_leaf_node():
                            _is_folder = True
                            area_files.append(_child_file)
                        # if _child_file.get_children().filter(id__in=file_list).count() > 0:
                        #     area_files.append(_child_file)
                        #     _children_files_sub = _child_file.get_descendants(include_self=False).iterator()
                        #     area_files.extend(_children_files_sub)

                    if _is_folder:
                        area = {
                            'project_id': project_id,
                            'name': file_instance.filename
                        }
                        try:
                            instance = cls.objects.create(**area)
                            instance.files.add(*area_files)
                            instance.save()
                        except Exception as e:
                            continue
                        if not _is_root:
                            parent_folders = file_instance.get_ancestors(ascending=True)
                            if parent_folders.exists():
                                parent_folder = parent_folders.first()
                                parent_area = Area.objects.filter(project_id=project_id, name=parent_folder.filename,
                                                                  files__in=parent_folder.get_children()).distinct()
                                if parent_area.exists():
                                    parent_area.first().dependencies.add(instance)

        return True


class AreaRelatedSerializer(DynamicFieldsRelatedSerializer):

    class Meta(object):
        model_class = Area
        model_serializer_class = AreaSerializer


class AreaLinksSerializer(serializers.Serializer):
    err_msg = {
        'does_not_exist': "Area with id {pk_value} doesn't exist."
    }
    main_area = AreaRelatedSerializer(fields='id', queryset=Area.objects.all(), error_messages=err_msg)
    linked_areas = AreaRelatedSerializer(fields='id', queryset=Area.objects.all(),
                                         many=True, error_messages=err_msg)

    def validate_linked_areas(self, areas):
        if len(areas) != len(set(areas)):
            areas_ids = ', '.join([str(area.id) for area in areas])
            raise serializers.ValidationError({'detail': "This areas list has duplicates: %s" % areas_ids})
        return areas


class AreaDependenciesMakerSerializer(serializers.Serializer):
    err_msg={
        'does_not_exist': "Area with id {pk_value} doesn't exist."
    }
    main_area = AreaRelatedSerializer(fields='id', queryset=Area.objects.all(), error_messages=err_msg)
    dependent_areas = AreaRelatedSerializer(fields='id', queryset=Area.objects.all(),
                                            many=True, error_messages=err_msg)

    def validate_dependent_areas(self, areas):
        if len(areas) != len(set(areas)):
            areas_ids = ', '.join([str(area.id) for area in areas])
            raise serializers.ValidationError({'detail': "This areas list has duplicates: %s" % areas_ids})
        return areas


class BranchSerializer(DynamicFieldsModelSerializer):

    class Meta(object):
        model = Branch
        fields = '__all__'


class ParentCommitSerializer(DynamicFieldsModelSerializer):
    id = serializers.ReadOnlyField(source='from_commit.id')
    display_id = serializers.ReadOnlyField(source='from_commit.display_id')
    repo_id = serializers.ReadOnlyField(source='from_commit.repo_id')
    url = serializers.ReadOnlyField(source='from_commit.url')

    class Meta(object):
        model = ParentCommit
        fields = ('id', 'display_id', 'repo_id', 'url')


class CommitSerializer(DynamicFieldsModelSerializer):

    parents = ParentCommitSerializer(source='to_commits', many=True, read_only=True)
    files = FileChangeSerializer(source='filechange_set', many=True, read_only=True)

    class Meta(object):
        model = Commit
        # fields = '__all__'
        exclude = ('branches',)


class CommitRelatedSerializer(DynamicFieldsRelatedSerializer):

    class Meta(object):
        model_class = Commit
        model_serializer_class = CommitSerializer


class TagSerializer(DynamicFieldsModelSerializer):
    target_type = serializers.CharField(source='target_type.name')
    target_object = GenericRelatedField({
        Commit: CommitSerializer(fields=('id', 'display_id', 'repo_id', 'url',), read_only=True),
    })

    class Meta(object):
        model = Tag
        fields = '__all__'


