# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models


from .abstract_models import AbstractProject
from .abstract_models import AbstractProjectOwner
from .abstract_models import AbstractProjectUser


class Project(AbstractProject):
    """
    Default Project model.
    """
    organization = models.ForeignKey('organization.Organization', related_name='projects', blank=False, null=False,
                                     on_delete=models.CASCADE)

    auto_area_on_commit = models.BooleanField(default=False)
    
    time_saving = models.IntegerField(default=0, blank=True,null=True)

    class Meta(AbstractProject.Meta):
        abstract = False


class ProjectUser(AbstractProjectUser):
    """
    Default ProjectUser model.
    """
    class Meta(AbstractProjectUser.Meta):
        abstract = False


class ProjectOwner(AbstractProjectOwner):
    """
    Default ProjectOwner model.
    """
    class Meta(AbstractProjectOwner.Meta):
        abstract = False
