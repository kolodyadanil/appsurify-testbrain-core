"""The model managers."""
from __future__ import absolute_import, unicode_literals
from datetime import timedelta
import sys
from celery import states
from celery.events.state import Task
from celery.utils.time import maybe_timedelta
from django.db import models, router, transaction, IntegrityError
from django.core import exceptions
from django.db.models.constants import LOOKUP_SEP
import six

from .utils import Now


class ExtendedQuerySet(models.QuerySet):
    """A custom model queryset that implements a few helpful methods."""

    def _create_object_from_params(self, lookup, params, lock=False):
        """
        Tries to create an object using passed params.
        Used by get_or_create and update_or_create
        """
        try:
            with transaction.atomic(using=self.db):
                params = {k: v() if callable(v) else v for k, v in params.items()}
                obj = self.create(**params)
            return obj, True
        except IntegrityError:
            exc_info = sys.exc_info()
            try:
                qs = self.select_for_update() if lock else self
                return qs.get(**lookup), False
            except self.model.DoesNotExist:
                pass
            six.reraise(*exc_info)

    def _extract_model_params(self, defaults, **kwargs):
        """
        Prepares `lookup` (kwargs that are valid model attributes), `params`
        (for creating a model instance) based on given kwargs; for use by
        get_or_create and update_or_create.
        """
        defaults = defaults or {}
        lookup = kwargs.copy()
        for f in self.model._meta.fields:
            if f.attname in lookup:
                lookup[f.name] = lookup.pop(f.attname)
        params = {k: v for k, v in kwargs.items() if LOOKUP_SEP not in k}
        params.update(defaults)
        property_names = self.model._meta._property_names
        invalid_params = []
        for param in params:
            try:
                self.model._meta.get_field(param)
            except exceptions.FieldDoesNotExist:
                # It's okay to use a model's property if it has a setter.
                if not (param in property_names and getattr(self.model, param).fset):
                    invalid_params.append(param)
        if invalid_params:
            raise exceptions.FieldError(
                "Invalid field name(s) for model %s: '%s'." % (
                    self.model._meta.object_name,
                    "', '".join(sorted(invalid_params)),
                ))
        return lookup, params

    def select_for_update_or_create(self, defaults=None, **kwargs):
        """Extend update_or_create with select_for_update.

        Look up an object with the given kwargs, updating one with defaults
        if it exists, otherwise create a new one.
        Return a tuple (object, created), where created is a boolean
        specifying whether an object was created.

        This is a backport from Django 1.11
        (https://code.djangoproject.com/ticket/26804) to support
        select_for_update when getting the object.
        """
        defaults = defaults or {}
        lookup, params = self._extract_model_params(defaults, **kwargs)
        self._for_write = True
        with transaction.atomic(using=self.db):
            try:
                obj = self.select_for_update().get(**lookup)
            except self.model.DoesNotExist:
                obj, created = self._create_object_from_params(lookup, params)
                if created:
                    return obj, created
            for k, v in defaults.items():
                setattr(obj, k, v() if callable(v) else v)
            obj.save(using=self.db)
        return obj, False


class WorkerStateQuerySet(ExtendedQuerySet):
    """A custom model queryset for the WorkerState model with some helpers."""

    def update_heartbeat(self, hostname, heartbeat, update_freq):
        with transaction.atomic():
            # check if there was an update in the last n seconds?
            interval = Now() - timedelta(seconds=update_freq)
            recent_worker_updates = self.filter(
                hostname=hostname,
                last_update__gte=interval,
            )
            if recent_worker_updates.exists():
                # if yes, get the latest update and move on
                obj = recent_worker_updates.get()
            else:
                # if no, update the worker state and move on
                obj, _ = self.select_for_update_or_create(
                    hostname=hostname,
                    defaults={'last_heartbeat': heartbeat},
                )
        return obj


class TaskStateQuerySet(ExtendedQuerySet):
    """A custom model queryset for the TaskState model with some helpers."""

    def active(self):
        """Return all active task states."""
        return self.filter(hidden=False)

    def expired(self, states, expires):
        """Return all expired task states."""
        return self.filter(
            state__in=states,
            tstamp__lte=Now() - maybe_timedelta(expires),
        )

    def expire_by_states(self, states, expires):
        """Expire task with one of the given states."""
        if expires is not None:
            return self.expired(states, expires).update(hidden=True)

    def purge(self):
        """Purge all expired task states."""
        with transaction.atomic():
            self.using(
                router.db_for_write(self.model)
            ).filter(hidden=True).delete()

    def update_state(self, state, task_id, defaults):
        with transaction.atomic():
            obj, created = self.select_for_update_or_create(
                task_id=task_id,
                defaults=defaults,
            )
            if created:
                return obj

            if states.state(state) < states.state(obj.state):
                keep = Task.merge_rules[states.RECEIVED]
            else:
                keep = {}
            for key, value in defaults.items():
                if key not in keep:
                    setattr(obj, key, value)
            obj.save(update_fields=tuple(defaults.keys()))
            return obj
