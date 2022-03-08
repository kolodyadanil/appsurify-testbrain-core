# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db.models import JSONField
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel

from applications.testing.models import TestRun, TestRunResult, Defect
from .tools.area_analyzer import AreaCodeAnalyzer


User = get_user_model()


class Area(models.Model):
    """
    Area model.
    """

    TYPE_UNKNOWN = 0
    TYPE_FOLDER = 1
    TYPE_CODE = 2

    TYPE_CHOICE = (
        (TYPE_UNKNOWN, 'unknown'),
        (TYPE_FOLDER, 'folder'),
        (TYPE_CODE, 'code'),
    )

    project = models.ForeignKey('project.Project', related_name='areas', blank=False, null=False,
                                on_delete=models.CASCADE)

    name = models.CharField(max_length=255, blank=False, null=False)
    usage = models.CharField(max_length=255, blank=True, null=False)
    type = models.IntegerField(default=TYPE_UNKNOWN, choices=TYPE_CHOICE, blank=False, null=False)
    priority = models.IntegerField(default=0, blank=False, null=False)

    dependencies = models.ManyToManyField('self', related_name='depended_on', blank=True, symmetrical=False)
    links = models.ManyToManyField('self', related_name='linked_to', blank=True, symmetrical=False)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta(object):
        unique_together = ('project', 'name')
        verbose_name = _(u'area')
        verbose_name_plural = _(u'areas')

    def __unicode__(self):
        return u'{id} {name}'.format(id=self.id, name=self.name)

    def get_all_files(self):
        return self.files.all()

    @classmethod
    def get_default(cls, project):
        area, created = cls.objects.get_or_create(project=project, name='Default Area')
        if created:
            area.usage = 'unknown'
            area.type = cls.TYPE_UNKNOWN
            area.priority = 1
            area.save()
        return area

    @classmethod
    def create_from_folders(cls, project_id):
        file_list = File.objects.filter(project_id=project_id).values_list('id', flat=True)

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

                    if _is_folder:
                        area = {
                            'project_id': project_id,
                            'name': file_instance.filename,
                            'type': cls.TYPE_FOLDER
                        }
                        try:
                            instance, created = cls.objects.get_or_create(**area)
                            instance.files.add(*area_files)
                            instance.save()
                        except Exception as e:
                            # print('exception from create from folders')
                            continue
                        if not _is_root:
                            parent_folders = file_instance.get_ancestors(ascending=True)
                            if parent_folders.exists():
                                parent_folder = parent_folders.first()
                                parent_area = Area.objects.filter(project_id=project_id, name=parent_folder.filename,
                                                                  type=cls.TYPE_FOLDER,
                                                                  files__in=parent_folder.get_children()).distinct()
                                if parent_area.exists():
                                    parent_area.first().dependencies.add(instance)

    @classmethod
    def create_from_code(cls, project, filename, patch=''):
        areas = list()
        try:
            analyzer = AreaCodeAnalyzer(filename=filename, content=patch)
            area_names = analyzer.analyze()
            with transaction.atomic():
                for area_name in area_names:
                    if not area_name:
                        continue
                    area, _ = cls.objects.get_or_create(project=project, name=area_name, type=cls.TYPE_CODE)
                    areas.append(area)
        except Exception as e:
            # print("DEBUG Print: {}".format(e))
            pass
        return areas

    @classmethod
    def get_by_filename(cls, project, filename):
        file_areas = list()

        if filename.startswith('/'):
            area_names = filename.split('/')[1:-1]
        else:
            area_names = filename.split('/')[0:-1]

        file_areas.extend(list(Area.objects.filter(project=project, name__in=area_names, type=cls.TYPE_FOLDER)))

        if len(file_areas) == 0 and project.auto_area_on_commit is True:
            area, _ = cls.objects.get_or_create(project=project, name=area_names[-1],
                                                defaults={'type': cls.TYPE_FOLDER})

            file_areas.append(area)

        default_area = cls.get_default(project=project)
        file_areas.append(default_area)

        return file_areas


class File(MPTTModel):
    """
    The file model stores the hierarchical structure and history of files in the project
    over which the changes were made.

    Properties describing the file:
        - project - a link to the record in the Project model by the master key. (ForeignKey)
        - areas - a multiple references to areas in the project. (Many2Many)
        - parent - a link to the parent record of the file, this may be the top level in the file path (directory).
        - sha - SHA hash of file in VCS repository.
        - filename - only filename without fullpath.
        - full_filename - full filename with full path.
        - raw_url - reserved for Github/BitBucket VCS repository for storing url for showing additional info.
        - blob_url - reserved for Github/BitBucket VCS repository for storing url for showing additional info.
        - contents_url - reserved for Github/BitBucket VCS repository for storing url for showing additional info.
        - created - a system field that is automatically populated when an object is created.
        It does not change in the future.
        - updated - a system field that is automatically populated when an object is created.
        Changed if the object is updated.

    Method `add_changes` have params:
        - commit - Commit model instance. Link to commit in which changes were made to this file.
        - additions - The number of addition lines in the file.
        - deletions - The number of deletion lines in the file.
        - changes - The number of changed lines in the file. (additions + deletetions)
        - status - File status. unknown/added/modified/deleted/renamed
        - patch - File patch.
        - blame - File blame.
        - previous_filename - The previous filename if file copy.

    Method `remove_changes` have params:
        - commit - Commit model instance. Link to commit in which changes were made to this file.

    """
    project = models.ForeignKey('project.Project', related_name='files', blank=False, null=False,
                                on_delete=models.CASCADE)
    areas = models.ManyToManyField('Area', related_name='files', blank=True)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')

    sha = models.CharField(max_length=255, default='', blank=True, null=False)

    filename = models.CharField(max_length=4096, default='', blank=True, null=False)
    full_filename = models.CharField(max_length=4096, default='', blank=True, null=False)

    raw_url = models.URLField(max_length=4096, default=str(), blank=True, null=False)
    blob_url = models.URLField(max_length=4096, default=str(), blank=True, null=False)
    contents_url = models.URLField(max_length=4096, default=str(), blank=True, null=False)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta(object):
        unique_together = ('project', 'filename', 'parent')
        verbose_name = _('Project file')
        verbose_name_plural = _('Project files')
        indexes = [
            models.Index(fields=['full_filename']),
        ]

    def __str__(self):
        return str('File: {id} {filename}'.format(id=self.id, filename=self.filename))

    def __unicode__(self):
        return u'File: {id} {filename}'.format(id=self.id, filename=self.filename)

    @classmethod
    def add_file_tree(cls, project, full_path, sha=''):
        created = False

        try:
            current_filename_instance = cls.objects.get(project=project, full_filename=full_path)
        except cls.DoesNotExist:
            full_filename_parts = full_path.split('/')

            default_area_id = Area.get_default(project).id

            parent = None
            current_filename_instance = None

            for filename in full_filename_parts:

                full_filename = '/'.join(full_filename_parts[:full_filename_parts.index(filename) + 1])

                try:
                    current_filename_instance = cls.objects.get(project=project, parent=parent, filename=filename)
                except cls.DoesNotExist:
                        current_filename_instance, created = cls.objects.update_or_create(project=project, parent=parent, filename=filename, defaults={'full_filename': full_filename})

                if current_filename_instance.parent:
                    if current_filename_instance.parent.get_descendant_count() - 1 == current_filename_instance.parent.get_descendants().filter(
                            areas__in=current_filename_instance.parent.areas.exclude(id=default_area_id)).count():
                        current_filename_instance.areas.add(
                            *current_filename_instance.parent.areas.exclude(id=default_area_id))

                parent = current_filename_instance

        if created or current_filename_instance.sha != sha:
            cls.objects.select_for_update().filter(id=current_filename_instance.id).update(sha=sha)

        return current_filename_instance

    def add_changes(self, commit, additions, deletions, changes, status, patch='', blame='', previous_filename=u''):
        """
        Method for adding information about file changes in a specific commit.
        An entry is created in the FileChange model.

        :param commit:
        :param additions:
        :param deletions:
        :param changes:
        :param status:
        :param patch:
        :param blame:
        :param previous_filename:
        :return:
        """
        if isinstance(patch, bytes):
            patch = patch.decode('utf8', errors='replace')

        if isinstance(blame, bytes):
            blame = blame.decode('utf8', errors='replace')

        if isinstance(previous_filename, bytes):
            previous_filename = previous_filename.decode('utf8', errors='replace')

        project_file_changes, created = FileChange.objects.get_or_create(file=self, commit=commit)
        project_file_changes.additions = additions
        project_file_changes.deletions = deletions
        project_file_changes.changes = changes
        project_file_changes.status = status

        project_file_changes.patch = patch.replace(chr(0x00), '')
        project_file_changes.blame = blame.replace(chr(0x00), '')
        project_file_changes.previous_filename = previous_filename.replace(chr(0x00), '')

        project_file_changes.save()

        return project_file_changes

    def remove_changes(self, commit):
        """
        Method for deleting information about file changes in a specific commit.
        An entry is removed in the FileChange model.
        :param commit:
        :return:
        """
        result = FileChange.objects.filter(commit=commit, file=self).delete()
        return result


class FileChange(models.Model):

    STATUS_UNKNOWN = 0
    STATUS_ADDED = 1
    STATUS_MODIFIED = 2
    STATUS_DELETED = 3
    STATUS_RENAMED = 4

    STATUS_CHOICE = (
        (STATUS_UNKNOWN, 'unknown'),
        (STATUS_ADDED, 'added'),
        (STATUS_MODIFIED, 'modified'),
        (STATUS_DELETED, 'deleted'),
        (STATUS_RENAMED, 'renamed'),
    )

    commit = models.ForeignKey('Commit', blank=False, null=False, on_delete=models.CASCADE)
    file = models.ForeignKey('File', blank=False, null=False, on_delete=models.CASCADE)

    additions = models.IntegerField(default=0, blank=False, null=False)
    deletions = models.IntegerField(default=0, blank=False, null=False)
    changes = models.IntegerField(default=0, blank=False, null=False)

    status = models.IntegerField(default=STATUS_ADDED, choices=STATUS_CHOICE, blank=False, null=False)

    patch = models.TextField(default='', blank=True, null=False)
    blame = models.TextField(default='', blank=True, null=False)

    previous_filename = models.CharField(max_length=4096, default='', blank=True, null=False)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta(object):
        verbose_name = _(u'project file changes')
        verbose_name_plural = _(u'project file changes')

    def __unicode__(self):
        return u'{id} {commit} {filename}'.format(id=self.id, commit=self.commit, filename=self.file.filename)


class Branch(models.Model):
    """

    """
    project = models.ForeignKey('project.Project', related_name='branches', blank=False, null=False,
                                on_delete=models.CASCADE)

    name = models.CharField(max_length=255, default='master', blank=False, null=False)
    sha = models.CharField(max_length=255, default='', blank=True, null=False)

    tags = GenericRelation('Tag', object_id_field='target_id', content_type_field='target_type')

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta(object):
        unique_together = ('project', 'name')
        verbose_name = _(u'branch')
        verbose_name_plural = _(u'branches')

    def __unicode__(self):
        return u'{id} {project} {name}'.format(id=self.id, project=self.project, name=self.name)

    @property
    def commit_count(self):
        return self.commits.count()


def get_default_user_dict():
    return dict(username=str(), first_name=str(), last_name=str(), email=str())


def get_default_stats():
    return dict(additions=0, deletions=0, total=0)


def get_default_tree():
    return dict(sha='', url='')


class Commit(models.Model):
    """

    """
    sender = models.ForeignKey(User, related_name='commits', blank=True, null=True, on_delete=models.CASCADE)

    project = models.ForeignKey('project.Project', related_name='commits', blank=False, null=False,
                                on_delete=models.CASCADE)
    areas = models.ManyToManyField('Area', related_name='commits', blank=True)

    branches = models.ManyToManyField('Branch', related_name='commits', blank=True)
    tags = GenericRelation('Tag', object_id_field='target_id', content_type_field='target_type')

    repo_id = models.CharField(max_length=255, default='', blank=True, null=False)  # Ex. 01f9c8680e9db9888463b61e423b7b1d18a5c2c1 equale sha field
    sha = models.CharField(max_length=255, default='', blank=True, null=False)

    display_id = models.CharField(max_length=255, default='0000000', blank=False, null=False)  # Ex. 01f9c86
    url = models.URLField(max_length=255, default=str(), blank=True, null=False)

    author = JSONField(default=get_default_user_dict, blank=False,
                       null=False)
    committer = JSONField(default=get_default_user_dict, blank=False,
                          null=False)

    message = models.CharField(max_length=255, default=str(), blank=True, null=False)  # Ex. NONE: Add groovy as java synhi\n+review @aahmed

    stats = JSONField(default=get_default_stats, blank=True, null=False)
    tree = JSONField(default=get_default_tree, blank=True, null=False)
    rework = models.IntegerField(default=0, blank=False, null=False)
    output = models.IntegerField(default=0, blank=False, null=False)
    riskiness = models.FloatField(default=0)

    files = models.ManyToManyField('File', through='FileChange', blank=True)
    parents = models.ManyToManyField('self', through='ParentCommit', symmetrical=False, blank=True)

    timestamp = models.DateTimeField(default=timezone.now, blank=False, null=False)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta(object):
        unique_together = ['project', 'sha', ]
        verbose_name = _(u'commit')
        verbose_name_plural = _(u'commits')
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['sha']),
        ]

    def __unicode__(self):
        return u'{id} {project} {display_id}'.format(id=self.id, project=self.project, display_id=self.display_id)

    def is_connected_with_commit(self, second_commit):
        """
        Method search routes('connections') between two commits.

        :param self: instance of commit
        :param second_commit: instance of commit
        :return: True if connection between commits exists, False if not.
        """
        if self.project != second_commit.project:
            raise ValueError('Both commits should be from one project.')

        if self.display_id == second_commit.display_id:
            return True

        if self.timestamp < second_commit.timestamp:
            ancestor = self
            descendant = second_commit
        else:
            ancestor = second_commit
            descendant = self

        ancestor_timestamp = ancestor.timestamp
        route_between_commits_is_founded = False
        common_branches = set(ancestor.branches.all()).intersection(descendant.branches.all())
        parent_exclude_condition = ~models.Q(branches__in=common_branches) | models.Q(timestamp__lt=ancestor_timestamp)
        parents_list = list(descendant.parents.exclude(parent_exclude_condition).order_by('-timestamp'))
        while len(parents_list) > 0:
            current_commit = parents_list.pop(0)
            if current_commit.display_id == ancestor.display_id:
                route_between_commits_is_founded = True
                break
            parents_list = list(
                current_commit.parents.exclude(parent_exclude_condition).order_by('-timestamp')
            ) + parents_list
        return route_between_commits_is_founded

    def add_parent(self, from_commit, index_number):
        """
        Method add parent commit to current instance of commit
        :param from_commit: parent instance commit
        :param index_number: number of sequence parent commits
        :return: parent commit instance
        """
        parent_commit, created = ParentCommit.objects.get_or_create(
            from_commit=from_commit,
            to_commit=self,
            index_number=index_number)
        return parent_commit

    def remove_parent(self, from_commit, index_number):
        """

        :param from_commit:
        :param index_number:
        :return:
        """
        result = ParentCommit.objects.filter(
            from_commit=from_commit,
            to_commit=self,
            index_number=index_number).delete()
        return result

    def sync_areas(self):
        files_areas = [area for area in set(self.files.all().values_list('areas', flat=True)) if area]
        self.areas.set(files_areas)


class ParentCommit(models.Model):
    """
    
    """
    to_commit = models.ForeignKey('Commit', related_name='to_commits', on_delete=models.CASCADE)
    from_commit = models.ForeignKey('Commit', related_name='from_commits', on_delete=models.CASCADE)
    index_number = models.IntegerField(default=0, blank=False, null=False)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta(object):
        verbose_name = _(u'parent commit')
        verbose_name_plural = _(u'parent commits')

    def __unicode__(self):
        return '{id} {index_number} {from_commit}'.format(id=self.id, index_number=self.index_number, from_commit=self.from_commit)


class Tag(models.Model):
    """
    Tag is an object to be marked with a commit. Tag is used to fix the version of the code.
    In github tag means release as is.
    The bitbucket tag means the version of the code, but there is no concept of release.
    And build means the testing and deployment process.

    As a general representation in most systems -
    Tag object indicating the state of the code at the time of
    its creation and return to the user in the archive.
    """

    sender = models.ForeignKey(User, related_name='tags', blank=True, null=True, on_delete=models.CASCADE)

    project = models.ForeignKey('project.Project', related_name='tags', blank=False, null=False,
                                on_delete=models.CASCADE)
    areas = models.ManyToManyField('Area', related_name='tags', blank=True)

    tag = models.CharField(max_length=255, default='0.0.1', blank=False, null=False)
    sha = models.CharField(max_length=255, default='', blank=True, null=False)
    url = models.URLField(max_length=255, default=str(), blank=True, null=False)
    tagger = JSONField(default=get_default_user_dict, blank=False, null=False)

    message = models.CharField(max_length=255, default=str(), blank=True, null=False)

    target_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.PositiveIntegerField()
    target_object = GenericForeignKey(ct_field='target_type', fk_field='target_id')

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta(object):
        unique_together = ('target_type', 'target_id')
        verbose_name = _(u'tag')
        verbose_name_plural = _(u'tags')

    def __unicode__(self):
        return u'{id} {tag}'.format(id=self.id, tag=self.tag)
