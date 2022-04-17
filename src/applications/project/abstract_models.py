# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import warnings

from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _
from .base_models import ProjMeta
from .base_models import AbstractBaseProject
from .base_models import AbstractBaseProjectUser
from .base_models import AbstractBaseProjectOwner
from .compat import reverse
from .compat import six
from .fields import AutoCreatedField
from .fields import AutoLastModifiedField
from .fields import SlugField
from .signals import project_user_added
from .signals import project_user_removed
from .signals import project_owner_changed


USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')
PROJS_TIMESTAMPED_MODEL = getattr(settings, 'PROJS_TIMESTAMPED_MODEL', None)


if PROJS_TIMESTAMPED_MODEL:
    warnings.warn('Configured TimestampModel has been replaced and is now ignored.', DeprecationWarning)


class SharedBaseModel(models.Model):
    """
    Adds fields ``created`` and ``updated`` and
    two private methods that are used by the rest
    of the abstract models.
    """
    created = AutoCreatedField()
    updated = AutoLastModifiedField()

    @property
    def _proj_user_model(self):
        model = self.__class__.module_registry[self.__class__.__module__]['ProjUserModel']
        if model is None:
            model = self.__class__.module_registry['project.models']['ProjUserModel']
        return model

    @property
    def _proj_owner_model(self):
        model = self.__class__.module_registry[self.__class__.__module__]['ProjOwnerModel']
        if model is None:
            model = self.__class__.module_registry['project.models']['ProjOwnerModel']
        return model

    class Meta(object):
        abstract = True


class AbstractProject(six.with_metaclass(ProjMeta, SharedBaseModel, AbstractBaseProject)):
    """
    Abstract Project model.
    """
    slug = SlugField(max_length=200, blank=False, editable=True,
                     populate_from='name', unique=True,
                     help_text=_("The name in all lowercase, suitable for URL identification"))

    class Meta(AbstractBaseProject.Meta):
        abstract = True
        verbose_name = _('project')
        verbose_name_plural = _('projects')

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('project_detail', kwargs={'project_pk': self.pk})

    def add(self, user, is_admin=False):
        proj_user = self._proj_user_model.objects.filter(user=user, project=self).exists()
        if proj_user:
            return proj_user
        return self.add_user(user=user, is_admin=is_admin)

    def add_user(self, user, is_admin=False):
        """
        Adds a new user and if the first user makes the user an admin and
        the owner.
        """
        users_count = self.users.all().count()
        if users_count == 0:
            is_admin = True

        # TODO: get specific proj user?
        proj_user = self._proj_user_model.objects.create(user=user,
                                                         project=self,
                                                         is_admin=is_admin)
        if users_count == 0:
            # TODO: get specific proj user?
            self._proj_owner_model.objects.create(project=self,
                                                  project_user=proj_user)

        # User added signal
        project_user_added.send(sender=self, user=user)
        return proj_user

    def remove(self, user):
        self.remove_user(user=user)

    def remove_user(self, user):
        """
        Deletes a user from an project.
        """
        proj_user = self._proj_user_model.objects.get(user=user, project=self)
        proj_user.delete()

        # User removed signal
        project_user_removed.send(sender=self, user=user)

    def get_or_add_user(self, user, **kwargs):
        """
        Adds a new user to the project, and if it's the first user makes
        the user an admin and the owner. Uses the `get_or_create` method to
        create or return the existing user.

        `user` should be a user instance, e.g. `auth.User`.

        Returns the same tuple as the `get_or_create` method, the
        `ProjectUser` and a boolean value indicating whether the
        ProjectUser was created or not.
        """
        is_admin = kwargs.pop('is_admin', False)
        users_count = self.users.all().count()
        if users_count == 0:
            is_admin = True

        proj_user, created = self._proj_user_model.objects.get_or_create(project=self,
                                                                         user=user,
                                                                         defaults={'is_admin': is_admin})
        if users_count == 0:
            self._proj_owner_model.objects.create(project=self, project_user=proj_user)
        if created:
            # User added signal
            project_user_added.send(sender=self, user=user)
        return proj_user, created

    def change_owner(self, new_owner):
        """
        Changes ownership of an project.
        """
        old_owner = self.owner.project_user
        self.owner.project_user = new_owner
        self.owner.save()

        # Owner changed signal
        project_owner_changed.send(sender=self, old=old_owner, new=new_owner)

    def is_admin(self, user):
        """
        Returns True is user is an admin in the project, otherwise false
        """
        return True if self.project_users.filter(user=user, is_admin=True) else False

    def is_owner(self, user):
        """
        Returns True is user is the project's owner, otherwise false
        """
        return self.owner.project_user.user == user


class AbstractProjectUser(six.with_metaclass(ProjMeta, SharedBaseModel, AbstractBaseProjectUser)):
    """
    Abstract ProjectUser model
    """
    is_admin = models.BooleanField(default=False)

    class Meta(AbstractBaseProjectUser.Meta):
        abstract = True
        verbose_name = _('project user')
        verbose_name_plural = _('project users')

    def __unicode__(self):
        return '{0} ({1})'.format(self.name if self.user.is_active else
                                  self.user.email, self.project.name)

    def delete(self, using=None):
        """
        If the project user is also the owner, this should not be deleted
        unless it's part of a cascade from the Project.

        If there is no owner then the deletion should proceed.
        """
        from .exceptions import OwnershipRequired
        try:
            if self.project.owner.project_user.id == self.id:
                raise OwnershipRequired(_('Cannot delete project owner before project or transferring ownership.'))
        # TODO: This line presumes that ProjOwner model can't be modified
        except self._proj_owner_model.DoesNotExist:
            pass
        super(AbstractBaseProjectUser, self).delete(using=using)

    def get_absolute_url(self):
        return reverse('project_user_detail', kwargs={
            'project_pk': self.project.pk, 'user_pk': self.user.pk})


class AbstractProjectOwner(six.with_metaclass(ProjMeta, SharedBaseModel, AbstractBaseProjectOwner)):
    """
    Abstract ProjectOwner model
    """
    class Meta(object):
        abstract = True
        verbose_name = _('project owner')
        verbose_name_plural = _('project owners')

    def save(self, *args, **kwargs):
        """
        Extends the default save method by verifying that the chosen
        project user is associated with the project.

        Method validates against the primary key of the project because
        when validating an inherited model it may be checking an instance of
        `Project` against an instance of `CustomProject`. Mutli-table
        inheritence means the database keys will be identical though.

        """
        from .exceptions import ProjectMismatch
        if self.project_user.project.pk != self.project.pk:
            raise ProjectMismatch
        else:
            super(AbstractBaseProjectOwner, self).save(*args, **kwargs)
