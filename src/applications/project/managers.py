# -*- coding: utf-8 -*-
from __future__ import unicode_literals


from django.db import models
from django.db.models import Q

class ProjQuerySet(models.QuerySet):

    def get_for_user(self, user):
        return self.filter(Q(users=user) | Q(is_public=True))


class ProjManager(models.Manager):

    def get_queryset(self):
        return ProjQuerySet(self.model, using=self._db)

    def get_for_user(self, user):
        if hasattr(self, 'get_queryset'):
            return self.get_queryset().filter(users=user)
        else:
            # Deprecated method for older versions of Django
            return self.get_query_set().filter(users=user)


class ActiveProjManager(ProjManager):
    """
    A more useful extension of the default manager which returns querysets
    including only active projects
    """

    def get_queryset(self):
        try:
            return super(ActiveProjManager, self).get_queryset().filter(is_active=True)
        except AttributeError:
            # Deprecated method for older versions of Django.
            return super(ActiveProjManager, self).get_query_set().filter(is_active=True)

    get_query_set = get_queryset
