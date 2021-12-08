# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from urllib.parse import urlunsplit

from applications.allauth.account.serializers import UserRelatedSerializer
from applications.api.vcs.serializers import *
from applications.testing.models import *
from applications.testing.tools import SpecFlow
from .stop_words import stop_words
from .wordinflector import WordInflector


class TestTypeSerializer(DynamicFieldsModelSerializer):
    project = ProjectRelatedSerializer(fields=('id', 'name'), queryset=Project.objects.all())

    class Meta(object):
        model = TestType
        fields = '__all__'


class TestTypeRelatedSerializer(DynamicFieldsRelatedSerializer):
    class Meta(object):
        model_class = TestType
        model_serializer_class = TestTypeSerializer


class TestSuiteSerializer(DynamicFieldsModelSerializer):
    project = ProjectRelatedSerializer(fields=('id', 'name'), queryset=Project.objects.all())
    test_type = TestTypeSerializer(fields=('id', 'name'), read_only=True)

    class Meta(object):
        model = TestSuite
        # fields = '__all__'
        exclude = ('tests',)

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

        if 'test_type' in self.initial_data:
            test_type = self.initial_data.get('test_type')
            if isinstance(test_type, dict):
                test_type_id = test_type.get('id', None)
                test_type_name = test_type.get('name', None)
                if test_type_id is None or test_type_id == '':
                    test_type_instance, created = TestType.objects.get_or_create(project=instance.project, name=test_type_name)
                else:
                    test_type_instance = TestType.objects.get(project=instance.project, id=test_type_id)
                instance.test_type = test_type_instance

            elif isinstance(test_type, int):
                test_type_instance = TestType.objects.get(project=instance.project, id=test_type)
                instance.test_type = test_type_instance

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

        if 'test_type' in self.initial_data:
            test_type = self.initial_data.get('test_type')
            if isinstance(test_type, dict):
                test_type_id = test_type.get('id', None)
                test_type_name = test_type.get('name', None)
                if test_type_id is None or test_type_id == '':
                    test_type_instance, created = TestType.objects.get_or_create(project=instance.project, name=test_type_name)
                else:
                    test_type_instance = TestType.objects.get(project=instance.project, id=test_type_id)
                instance.test_type = test_type_instance

            elif isinstance(test_type, int):
                test_type_instance = TestType.objects.get(project=instance.project, id=test_type)
                instance.test_type = test_type_instance

        # Save many-to-many relationships after the instance is created.
        if many_to_many:
            for field_name, value in many_to_many.items():
                field = getattr(instance, field_name)
                field.set(value)

        instance.save()
        return instance


class TestSuiteRelatedSerializer(DynamicFieldsRelatedSerializer):

    class Meta(object):
        model_class = TestSuite
        model_serializer_class = TestSuiteSerializer


class TestRunSerializer(DynamicFieldsModelSerializer):

    project = ProjectRelatedSerializer(fields=('id', 'name'), queryset=Project.objects.all())
    test_suite = TestSuiteRelatedSerializer(fields=('id', 'name'), queryset=TestSuite.objects.all())
    meta = serializers.ListField(child=serializers.CharField(default=str(),
                                                             allow_blank=True, allow_null=True),
                                 default=list(), allow_null=True, allow_empty=True, required=False)

    class Meta(object):
        model = TestRun
        # fields = '__all__'
        exclude = ('extra_data', 'areas',)


class TestRunRelatedSerializer(DynamicFieldsRelatedSerializer):
    class Meta(object):
        model_class = TestRun
        model_serializer_class = TestRunSerializer


class StepSerializer(DynamicFieldsModelSerializer):
    project = ProjectRelatedSerializer(fields=('id', 'name'), queryset=Project.objects.all())

    class Meta(object):
        model = Step
        fields = '__all__'


class StepRelatedSerializer(DynamicFieldsRelatedSerializer):
    class Meta(object):
        model_class = Step
        model_serializer_class = StepSerializer


class TestStepSerializer(DynamicFieldsModelSerializer):

    id = serializers.ReadOnlyField(source='step.id')
    name = serializers.ReadOnlyField(source='step.name')

    class Meta(object):
        model = TestStep
        fields = ('id', 'name', 'index_number',)


class PredictedSearchTestMixin(object):

    def get_predicted_areas(self, obj):
        associated_areas = list(obj.associated_areas.all().values('id', 'name'))

        project_areas = Area.objects.filter(project=obj.project).exclude(id__in=(x['id'] for x in associated_areas))
        project_areas = project_areas.exclude(name__in=stop_words)
        project_areas = project_areas.annotate(name_lower=Lower('name'))
        project_areas = list(project_areas.values('id', 'name', 'name_lower'))

        searched_words = obj.name.split(' ')
        searched_words += obj.class_name and obj.class_name.split(' ') or []
        searched_words += obj.area and obj.area.name.split(' ') or []
        searched_words = [word.lower() for word in searched_words if word not in stop_words]
        searched_words = WordInflector().normalize_words(searched_words)
        searched_words = set(searched_words)
        matched_areas = []
        for word in searched_words:
            for cur_area in project_areas:
                if cur_area['name_lower'].find(word) != -1 or word.find(cur_area['name_lower']) != -1:
                    matched_areas.append([x for x in cur_area.items() if x[0] != 'name_lower'])
        matched_areas = [dict(t) for t in {tuple(l) for l in matched_areas}]
        return associated_areas, matched_areas

    def get_predicted_files(self, obj):
        associated_files = list(obj.associated_files.exclude(sha='').values('id', 'filename', 'full_filename'))
        query = Q(project=obj.project) & ~Q(sha='') & ~Q(id__in=(x['id'] for x in associated_files))
        project_files = File.objects.exclude(filename__in=stop_words)
        project_files = project_files.annotate(filename_lower=Lower('filename'))
        project_files = project_files.filter(query).values('id', 'filename', 'full_filename', 'filename_lower')

        searched_words = obj.name.split(' ')
        searched_words += obj.class_name and obj.class_name.split(' ') or []
        searched_words += obj.area and obj.area.name.split(' ') or []
        searched_words = [x.lower() for x in searched_words if x not in stop_words]
        searched_words = WordInflector().normalize_words(searched_words)
        searched_words = set(searched_words)

        matched_files = []
        for word in searched_words:
            for cur_file in project_files:
                file_name = cur_file['filename_lower']
                file_name = file_name[1:] if file_name[0] == '.' else file_name
                file_name = file_name.rsplit('.', 1)[0]
                if file_name.find(word) != -1 or word.find(file_name) != -1:
                    matched_files.append([x for x in cur_file.items() if x[0] != 'filename_lower'])
        matched_files = [dict(t) for t in {tuple(l) for l in matched_files}]

        return associated_files, matched_files


class TestSerializer(DynamicFieldsModelSerializer, PredictedSearchTestMixin):

    # project = ProjectRelatedSerializer(fields=('id', 'name'), queryset=Project.objects.all())
    # test_suite = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    steps = TestStepSerializer(source='teststep_set', many=True, read_only=True)

    tags = serializers.ListField(default=list(), allow_empty=True, required=False)
    lines = serializers.ListField(default=list(), allow_empty=True, required=False)
    parameters = serializers.ListField(default=list(), allow_empty=True, required=False)
    meta = serializers.ListField(default=list(), allow_empty=True, required=False)
    predicted_areas = serializers.SerializerMethodField()
    predicted_files = serializers.SerializerMethodField()
    is_auto_assigned = serializers.SerializerMethodField()

    class Meta(object):
        model = Test
        fields = '__all__'
        # exclude = ('steps',)

    def get_is_auto_assigned(self, obj):
        associated_files = obj.associated_files.filter(~Q(sha='')).values('id', 'filename', 'full_filename')
        associated_areas = obj.associated_areas.all().values('id', 'name')

        if associated_files or associated_areas:
            return True
        else:
            return False

    def get_predicted_areas(self, *args, **kwargs):
        associated_areas, matched_areas = super(TestSerializer, self).get_predicted_areas(*args, **kwargs)
        return associated_areas + matched_areas

    def get_predicted_files(self, *args, **kwargs):
        associated_files, matched_files = super(TestSerializer, self).get_predicted_files(*args, **kwargs)
        return associated_files + matched_files

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

        if 'steps' in self.initial_data:
            TestStep.objects.filter(test=instance).delete()
            steps = self.initial_data.get('steps')
            for step in steps:
                step_id = step.get('id')
                step_name = step.get('name')
                step_index_number = step.get('index_number')
                step_instance, created = Step.objects.get_or_create(project=instance.project, name=step_name)
                instance.add_step(step_instance, index_number=step_index_number)

        if 'test_suite' in self.initial_data:
            test_suite_id = self.initial_data.get('test_suite')
            test_suite = TestSuite.objects.get(id=test_suite_id)
            test_suite.tests.add(instance)

        files = self.initial_data.get('associated_files')
        file_list = list()
        for file in files:
            file_list.append(file)
        file_trees = list()

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
                        file_trees.append(file_instance)
                        _children_files = file_instance.get_children().filter(id__in=file_list).iterator()
                        file_trees.extend(_children_files)
                    elif file_instance.get_children().filter(id__in=file_list).count() == 0:
                        file_trees.append(file_instance)
                        _children_files = file_instance.get_descendants(include_self=False).iterator()
                        file_trees.extend(_children_files)
                    else:
                        pass

                # PREPARE MIDDLE NODES
                elif _is_child and not _is_leaf:
                    if file_instance.id in file_list:
                        if file_instance.parent_id in file_list:
                            if file_instance.get_children().filter(id__in=file_list).count() > 0:
                                file_trees.append(file_instance)
                                _children_files = file_instance.get_children().filter(id__in=file_list).iterator()
                                file_trees.extend(_children_files)
                            elif file_instance.get_children().filter(id__in=file_list).count() == 0:
                                file_trees.append(file_instance)
                                _children_files = file_instance.get_descendants(include_self=False).iterator()
                                file_trees.extend(_children_files)
                            else:
                                pass

                # PREPARE LEAF NODE
                elif file_instance.is_leaf_node():
                    if file_instance.parent_id in file_list:
                        file_trees.append(file_instance)
        instance.associated_files.set([])
        instance.associated_files.add(*file_trees)

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

        if 'steps' in self.initial_data:
            steps = self.initial_data.get('steps')
            for step in steps:
                step_id = step.get('id')
                step_name = step.get('name')
                step_index_number = step.get('index_number')
                step_instance, created = Step.objects.get_or_create(project=instance.project, name=step_name)
                instance.add_step(step_instance, index_number=step_index_number)

        if 'test_suite' in self.initial_data:
            test_suite_id = self.initial_data.get('test_suite')
            test_suite = TestSuite.objects.get(id=test_suite_id)
            test_suite.tests.add(instance)

        # Save many-to-many relationships after the instance is created.
        if many_to_many:
            for field_name, value in many_to_many.items():
                field = getattr(instance, field_name)
                field.set(value)

        instance.save()
        return instance


class TestRelatedSerializer(DynamicFieldsRelatedSerializer):

    class Meta(object):
        model_class = Test
        model_serializer_class = TestSerializer


class TestRunResultSerializer(DynamicFieldsModelSerializer):
    project = ProjectRelatedSerializer(fields=('id', 'name'), queryset=Project.objects.all())
    test_type = TestTypeRelatedSerializer(fields=('id', 'name'), queryset=TestType.objects.all())
    test_suite = TestSuiteRelatedSerializer(fields=('id', 'name'), queryset=TestSuite.objects.all())
    test_run = TestRunRelatedSerializer(fields=('id', 'name'), queryset=TestRun.objects.all())
    test = TestRelatedSerializer(fields=('id', 'name'), queryset=Test.objects.all())
    area = AreaRelatedSerializer(fields=('id', 'name'), queryset=Area.objects.all())
    step = StepRelatedSerializer(fields=('id', 'name'), queryset=Step.objects.all(), required=False, allow_null=True, allow_empty=True)
    commit = CommitRelatedSerializer(fields=('id', 'display_id'), queryset=Commit.objects.all(), required=False, allow_null=True, allow_empty=True)

    class Meta(object):
        model = TestRunResult
        fields = (
        'id',
        'project',
        'test_type',
        'test_suite',
        'test_run',
        'test',
        'area',
        'step',
        'commit',
        'execution_started',
        'execution_ended', 'is_local', 'status', 'result', 'stacktrace', 'failure_message', 'log')
        # fields = '__all__'


class DefectSerializer(DynamicFieldsModelSerializer):

    project = ProjectRelatedSerializer(fields=('id', 'name'), queryset=Project.objects.all())
    owner = UserRelatedSerializer(fields=('id', 'username'), queryset=User.objects.all(), required=False)

    priority = serializers.IntegerField(default=1, min_value=1, max_value=10)

    associated_tests = TestRelatedSerializer(fields=('id', 'name'), queryset=Test.objects.all(), many=True)

    passed_associated_tests = serializers.ListSerializer(
        child=TestRelatedSerializer(fields=('id', 'name',), read_only=True),
        read_only=True,
        allow_null=True,
        allow_empty=True
    )
    failed_associated_tests = serializers.ListSerializer(
        child=TestRelatedSerializer(fields=('id', 'name',), read_only=True),
        read_only=True,
        allow_null=True,
        allow_empty=True
    )
    broken_associated_tests = serializers.ListSerializer(
        child=TestRelatedSerializer(fields=('id', 'name',), read_only=True),
        read_only=True,
        allow_null=True,
        allow_empty=True
    )
    not_run_associated_tests = serializers.ListSerializer(
        child=TestRelatedSerializer(fields=('id', 'name',), read_only=True),
        read_only=True,
        allow_null=True,
        allow_empty=True
    )

    found_commits = CommitRelatedSerializer(fields=('id', 'display_id', 'message', 'url'), queryset=Commit.objects.all(), many=True, required=False, allow_empty=True, allow_null=True)

    created_by_commit = CommitRelatedSerializer(fields=('id', 'display_id', 'message', 'url'), queryset=Commit.objects.all(), required=False, allow_empty=True, allow_null=True)

    caused_by_commits = CommitRelatedSerializer(fields=('id', 'display_id', 'message', 'url'), queryset=Commit.objects.all(), many=True, required=False, allow_empty=True, allow_null=True)

    closed_by_commits = CommitRelatedSerializer(fields=('id', 'display_id', 'message', 'url'), queryset=Commit.objects.all(), many=True, required=False, allow_empty=True, allow_null=True)

    class Meta(object):
        model = Defect
        fields = '__all__'


class TestAssociateSerializer(DynamicFieldsModelSerializer, PredictedSearchTestMixin):
    class Meta(object):
        model = Test
        fields = ('id',)

    def auto_assign(self):
        tests = self.context.get('tests')
        for test in tests:
            _, matched_areas = super(TestAssociateSerializer, self).get_predicted_areas(test)
            test.associated_areas.add(*Area.objects.filter(id__in=(x['id'] for x in matched_areas)))

            associated_files, matched_files = super(TestAssociateSerializer, self).get_predicted_files(test)
            associated_files = [x['id'] for x in associated_files]
            file_list = [x['id'] for x in matched_files]
            file_trees = list()
            _files = File.objects.filter(id__in=file_list).order_by('tree_id')
            for file_instance in _files:
                _is_root = file_instance.is_root_node()
                _is_child = file_instance.is_child_node()
                _is_leaf = file_instance.is_leaf_node()

                if _is_root or _is_child and not _is_leaf:
                    _file_tree = file_instance.get_descendants(include_self=True)
                    file_trees.extend(_file_tree.exclude(id__in=associated_files).iterator())
                elif file_instance.is_leaf_node():
                    file_trees.append(file_instance)

            if len(file_trees) != 0:
                test.associated_files.add(*set(file_trees))

    def save(self):
        tests = self.context.get('tests')
        files = self.context.get('files')
        areas = self.context.get('areas')

        test_list = list()
        area_list = list()
        file_list = list()

        for test in tests:
            test_list.append(test)
        for area in areas:
            area_list.append(area)
        for file in files:
            file_list.append(file)

        file_trees = list()

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
                        file_trees.append(file_instance)
                        _children_files = file_instance.get_children().filter(id__in=file_list).iterator()
                        file_trees.extend(_children_files)
                    elif file_instance.get_children().filter(id__in=file_list).count() == 0:
                        file_trees.append(file_instance)
                        _children_files = file_instance.get_descendants(include_self=False).iterator()
                        file_trees.extend(_children_files)
                    else:
                        pass

                # PREPARE MIDDLE NODES
                elif _is_child and not _is_leaf:
                    if file_instance.id in file_list:
                        if file_instance.parent_id in file_list:
                            if file_instance.get_children().filter(id__in=file_list).count() > 0:
                                file_trees.append(file_instance)
                                _children_files = file_instance.get_children().filter(id__in=file_list).iterator()
                                file_trees.extend(_children_files)
                            elif file_instance.get_children().filter(id__in=file_list).count() == 0:
                                file_trees.append(file_instance)
                                _children_files = file_instance.get_descendants(include_self=False).iterator()
                                file_trees.extend(_children_files)
                            else:
                                pass

                # PREPARE LEAF NODE
                elif file_instance.is_leaf_node():
                    if file_instance.parent_id in file_list:
                        file_trees.append(file_instance)
        
        _tests = Test.objects.filter(id__in=test_list)
        for test_instance in _tests:
            current_files = test_instance.associated_files.all()
            current_areas = test_instance.associated_areas.all()

            for current_file in current_files:
                test_instance.associated_files.remove(current_file.id)
            for current_area in current_areas:
                test_instance.associated_areas.remove(current_area.id)
            
            test_instance.associated_files.add(*file_trees)
            test_instance.associated_areas.add(*area_list)
            test_instance.save()
        
        return True


class ImportTestingReportSerializer(serializers.Serializer):

    def save(self, request):
        user = request.user

        validated_data = self.validated_data

        project = validated_data['project']
        test_suite = validated_data['test_suite']
        commit = validated_data.get('commit', None)
        file = validated_data['file']
        type = validated_data['type']
        test_run_name = validated_data.get('test_run_name', None)
        utils = SpecFlow.ImportUtils(
            type_xml=type,
            file_obj=file,
            data=dict(project=project, test_suite=test_suite, commit=commit),
            user_id=user.id,
            test_run_name=test_run_name,
            host=urlunsplit((request.scheme, request.get_host(), '/test-runs/', None, None))
        )
        result = utils.import_xml_tests()
        return result

    project = ProjectRelatedSerializer(fields=('id', 'name'), queryset=Project.objects.all(), many=False)
    test_suite = TestSuiteRelatedSerializer(fields=('id', 'name'), queryset=TestSuite.objects.all(), write_only=True)
    commit = CommitRelatedSerializer(fields=('id', 'display_id'), queryset=Commit.objects.all(), many=False, required=False, allow_null=True, allow_empty=True)
    type = serializers.ChoiceField(choices=SpecFlow.ALLOWED_FORMAT_TYPES, required=True)
    test_run_name = serializers.CharField(max_length=255, allow_blank=True, allow_null=True, required=False)
    file = serializers.FileField(required=True)


class OutputImportSerializer(serializers.Serializer):
    new_defects = serializers.IntegerField(default=0)
    flaky_defects = serializers.IntegerField(default=0)
    reopened_defects = serializers.IntegerField(default=0)
    reopened_flaky_defects = serializers.IntegerField(default=0)
    flaky_failures_breaks = serializers.IntegerField(default=0)

    failed_tests = serializers.IntegerField(default=0)
    broken_tests = serializers.IntegerField(default=0)
    skipped_tests = serializers.IntegerField(default=0)
    passed_tests = serializers.IntegerField(default=0)

    report_url = serializers.CharField(default=str())


class ImportDefectsSerializer(serializers.Serializer):
    project_id = serializers.SerializerMethodField()
