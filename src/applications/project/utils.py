# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from itertools import chain


def default_proj_model():
    """Encapsulates importing the concrete model"""
    from applications.project.models import Project
    return Project


def model_field_names(model):
    """
    Returns a list of field names in the model

    Direct from Django upgrade migration guide.
    """
    return list(set(chain.from_iterable(
        (field.name, field.attname) if hasattr(field, 'attname') else (field.name,)
        for field in model._meta.get_fields()
        if not (field.many_to_one and field.related_model is None)
    )))


def create_project(user, name, is_active=None, proj_defaults=None, proj_user_defaults=None, **kwargs):
    """
    Returns a new project, also creating an initial project user who
    is the owner.

    The specific models can be specified if a custom project app is used.
    The simplest way would be to use a partial.

    """
    proj_model = kwargs.pop('model', None) or kwargs.pop('proj_model', None) or default_proj_model()
    kwargs.pop('proj_user_model', None)  # Discard deprecated argument

    proj_owner_model = proj_model.owner.related.related_model
    try:
        # Django 1.9
        proj_user_model = proj_model.project_users.rel.related_model
    except AttributeError:
        # Django 1.8
        proj_user_model = proj_model.project_users.related.related_model

    if proj_defaults is None:
        proj_defaults = {}
    if proj_user_defaults is None:
        if 'is_admin' in model_field_names(proj_user_model):
            proj_user_defaults = {'is_admin': True}
        else:
            proj_user_defaults = {}

    if is_active is not None:
        proj_defaults.update({'is_active': is_active})

    proj_defaults.update({'name': name})
    project = proj_model.objects.create(**proj_defaults)

    proj_user_defaults.update({'project': project, 'user': user})
    new_user = proj_user_model.objects.create(**proj_user_defaults)

    proj_owner_model.objects.create(project=project, project_user=new_user)
    return project


def model_field_attr(model, model_field, attr):
    """
    Returns the specified attribute for the specified field on the model class.
    """
    fields = dict([(field.name, field) for field in model._meta.fields])
    return getattr(fields[model_field], attr)
