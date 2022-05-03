# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.dispatch
from django.dispatch import receiver
from django.db.models.signals import pre_save, post_save, m2m_changed
from django.contrib.auth import get_user_model


User = get_user_model()


project_user_kwargs = {'providing_args': ['user']}
project_user_added = django.dispatch.Signal(**project_user_kwargs)
project_user_removed = django.dispatch.Signal(**project_user_kwargs)

project_owner_kwargs = {'providing_args': ['old', 'new']}
project_owner_changed = django.dispatch.Signal(**project_owner_kwargs)


# from applications.testing.models import TestType
# from applications.vcs.models import Area
# from applications.project.models import Project
#
#
# @receiver(post_save, sender=Project)
# def model_project_autocreate_defaults(sender, instance, created, **kwargs):
#     project = instance
#     TestType.get_default(project=project)
#     Area.get_default(project=project)
