# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from importlib import import_module

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.utils.timezone import now


class AutoCreatedField(models.DateTimeField):
    """
    A DateTimeField that automatically populates itself at
    object creation.

    By default, sets editable=False, default=datetime.now.

    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('editable', False)
        kwargs.setdefault('default', now)
        super(AutoCreatedField, self).__init__(*args, **kwargs)


class AutoLastModifiedField(AutoCreatedField):
    """
    A DateTimeField that updates itself on each save() of the model.

    By default, sets editable=False and default=datetime.now.

    """
    def pre_save(self, model_instance, add):
        value = now()
        setattr(model_instance, self.attname, value)
        return value


ORGS_SLUGFIELD = getattr(settings, 'ORGS_SLUGFIELD', 'django_extensions.db.fields.AutoSlugField')

try:
    module, klass = ORGS_SLUGFIELD.rsplit('.', 1)
    BaseSlugField = getattr(import_module(module), klass)
except (ImportError, ValueError):
    raise ImproperlyConfigured("Your SlugField class, '{0}', is improperly defined. "
                   "See the documentation and install an auto slug field".format(ORGS_SLUGFIELD))


class SlugField(BaseSlugField):
    """Class redefinition for migrations"""
