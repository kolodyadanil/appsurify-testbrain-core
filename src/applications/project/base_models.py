# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models.base import ModelBase
from django.utils.translation import ugettext_lazy as _
from .compat import six
from .managers import ActiveProjManager
from .managers import ProjManager


USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')


class UnicodeMixin(object):
    """
    Python 2 and 3 string representation support.
    """
    def __str__(self):
        if six.PY3:
            return self.__unicode__()
        else:
            return unicode(self).encode('utf-8')


class ProjMeta(ModelBase):
    """
    Base metaclass for dynamically linking related project models.

    This is particularly useful for custom projects that can avoid
    multitable inheritence and also add additional attributes to the
    project users especially.

    The `module_registry` dictionary is used to track the architecture across
    different Django apps. If more than one application makes use of these
    base models, the extended models will share class relationships, which is
    clearly undesirable. This ensures that the relationships between models
    within a module using these base classes are from other project models.

    """
    module_registry = {}

    def __new__(cls, name, bases, attrs):  # noqa
        # Borrowed from Django-polymorphic
        # Workaround compatibility issue with six.with_metaclass() and custom
        # Django model metaclasses:
        if not attrs and name == 'NewBase':
            return super(ProjMeta, cls).__new__(cls, name, bases, attrs)

        base_classes = ['ProjModel', 'ProjUserModel', 'ProjOwnerModel']
        model = super(ProjMeta, cls).__new__(cls, name, bases, attrs)
        module = model.__module__
        if not cls.module_registry.get(module):
            cls.module_registry[module] = {
                'ProjModel': None,
                'ProjUserModel': None,
                'ProjOwnerModel': None,
            }
        for b in bases:
            key = None
            if b.__name__ in ['AbstractProject', 'ProjectBase']:
                key = 'ProjModel'
            elif b.__name__ in ['AbstractProjectUser', 'ProjectUserBase']:
                key = 'ProjUserModel'
            elif b.__name__ in ['AbstractProjectOwner', 'ProjectOwnerBase']:
                key = 'ProjOwnerModel'
            if key:
                cls.module_registry[module][key] = model

        if all([cls.module_registry[module][klass] for klass in base_classes]):
            model.update_proj(module)
            model.update_proj_users(module)
            model.update_proj_owner(module)

        return model

    def update_proj(cls, module):
        """
        Adds the `users` field to the project model
        """
        try:
            cls.module_registry[module]['ProjModel']._meta.get_field('users')
        except FieldDoesNotExist:
            cls.module_registry[module]['ProjModel'].add_to_class('users',
                models.ManyToManyField(USER_MODEL,
                        through=cls.module_registry[module]['ProjUserModel'].__name__,
                        related_name='%(app_label)s_%(class)s'))

    def update_proj_users(cls, module):
        """
        Adds the `user` field to the project user model and the link to
        the specific project model.
        """
        try:
            cls.module_registry[module]['ProjUserModel']._meta.get_field('user')
        except FieldDoesNotExist:
            cls.module_registry[module]['ProjUserModel'].add_to_class('user',
                models.ForeignKey(USER_MODEL, related_name='%(app_label)s_%(class)s', on_delete=models.DO_NOTHING))
        try:
            cls.module_registry[module]['ProjUserModel']._meta.get_field('project')
        except FieldDoesNotExist:
            cls.module_registry[module]['ProjUserModel'].add_to_class('project',
                models.ForeignKey(cls.module_registry[module]['ProjModel'],
                        related_name='project_users', on_delete=models.DO_NOTHING))

    def update_proj_owner(cls, module):
        """
        Creates the links to the project and project user for the owner.
        """
        try:
            cls.module_registry[module]['ProjOwnerModel']._meta.get_field('project_user')
        except FieldDoesNotExist:
            cls.module_registry[module]['ProjOwnerModel'].add_to_class('project_user',
                models.OneToOneField(cls.module_registry[module]['ProjUserModel'], on_delete=models.DO_NOTHING))
        try:
            cls.module_registry[module]['ProjOwnerModel']._meta.get_field('project')
        except FieldDoesNotExist:
            cls.module_registry[module]['ProjOwnerModel'].add_to_class('project',
                models.OneToOneField(cls.module_registry[module]['ProjModel'],
                        related_name='owner', on_delete=models.DO_NOTHING))


class AbstractBaseProject(UnicodeMixin, models.Model):
    """
    The umbrella object with which users can be associated.

    An project can have multiple users but only one who can be designated
    the owner user.
    """

    name = models.CharField(max_length=200, help_text=_('The name of the project'))
    is_public = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = ProjManager()
    active = ActiveProjManager()

    class Meta(object):
        abstract = True
        ordering = ['name']

    def __unicode__(self):
        return self.name

    @property
    def user_relation_name(self):
        """
        Returns the string name of the related name to the user.

        This provides a consistent interface across different project
        model classes.
        """
        return "{0}_{1}".format(self._meta.app_label.lower(),
                self.__class__.__name__.lower())

    def is_member(self, user):
        return True if user in self.users.all() else False


class ProjectBase(six.with_metaclass(ProjMeta, AbstractBaseProject)):
    class Meta(AbstractBaseProject.Meta):
        abstract = True


class AbstractBaseProjectUser(UnicodeMixin, models.Model):
    """
    ManyToMany through field relating Users to Projects.

    It is possible for a User to be a member of multiple projects, so this
    class relates the ProjectUser to the User model using a ForeignKey
    relationship, rather than a OneToOne relationship.

    Authentication and general user information is handled by the User class
    and the contrib.auth application.
    """

    class Meta(object):
        abstract = True
        ordering = ['project', 'user']
        unique_together = ('project', 'user')

    def __unicode__(self):
        return u"{0} ({1})".format(self.user.get_full_name() if self.user.is_active else
                self.user.email, self.project.name)

    @property
    def name(self):
        """
        Returns the connected user's full name or string representation if the
        full name method is unavailable (e.g. on a custom user class).
        """
        if hasattr(self.user, 'get_full_name'):
            return self.user.get_full_name()
        return "{0}".format(self.user)


class ProjectUserBase(six.with_metaclass(ProjMeta, AbstractBaseProjectUser)):
    class Meta(AbstractBaseProjectUser.Meta):
        abstract = True


class AbstractBaseProjectOwner(UnicodeMixin, models.Model):
    """
    Each project must have one and only one project owner.
    """

    class Meta(object):
        abstract = True

    def __unicode__(self):
        return u"{0}: {1}".format(self.project, self.project_user)


class ProjectOwnerBase(six.with_metaclass(ProjMeta, AbstractBaseProjectOwner)):
    class Meta(AbstractBaseProjectOwner.Meta):
        abstract = True
