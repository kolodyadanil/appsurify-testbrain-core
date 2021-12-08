# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import uuid
import base64
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _


User = get_user_model()


class LicenseKeyQuerySet(models.QuerySet):

    def active(self):
        return self.filter(Q(expired=None) | Q(expired__gte=timezone.now()))


class LicenseKeyManager(models.Manager):
    use_in_migrations = True

    def get_queryset(self):
        return LicenseKeyQuerySet(self.model, using=self._db)

    def _create(self, organization, balance, expired, **extra_fields):

        if extra_fields.get('default') is True:
            if organization.license_keys.filter(default=True).exists():
                raise ValueError('There can be only one default key.')

        user = None
        if organization.owner:
            user = organization.owner.organization_user.user

        license_key = self.model(organization=organization,
                                 user=user,
                                 balance=balance,
                                 expired=expired, **extra_fields)
        license_key.save(using=self._db)
        return license_key

    def create_default(self, organization, **extra_fields):

        extra_fields.setdefault('default', True)
        extra_fields.setdefault('balance', settings.DEFAULT_LICENSE_BALANCE)
        extra_fields.setdefault('expired', None)

        if extra_fields.get('default') is not True:
            raise ValueError('Default license key value must have default=True.')

        if extra_fields.get('expired') is not None:
            raise ValueError('Default license key value must have expired=None.')

        return self._create(organization, **extra_fields)

    def create_extra(self, organization, balance=None, expired=None, uuid=None, **extra_fields):

        extra_fields.setdefault('default', False)

        if extra_fields.get('default') is not False:
            raise ValueError('Extra license key value must have default=False.')

        if balance is None:
            raise ValueError('Extra license key value must have balance > 0 and not None.')

        if expired is None:
            raise ValueError('Extra license key value must have expired not None.')

        return self._create(organization, balance, expired, uuid=uuid, **extra_fields)


class LicenseKey(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    organization = models.ForeignKey('organization.Organization', related_name='license_keys', blank=False, null=False,
                                     on_delete=models.DO_NOTHING)
    user = models.ForeignKey(User, related_name='license_keys', blank=True, null=True, on_delete=models.SET_NULL)

    default = models.BooleanField(default=False)

    balance = models.IntegerField('time balance', default=0, blank=False, null=False)

    expired = models.DateTimeField(blank=True, null=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = LicenseKeyManager()

    class Meta(object):
        verbose_name = _(u'license key')
        verbose_name_plural = _(u'licenses keys')

    def _dict(self):
        return {
            'site': {'name': self.organization.site.name, 'domain': self.organization.site.domain},
            'organization': {'name': self.organization.name, 'slug': self.organization.slug, 'type': self.organization.type},
            'user': {'username': self.user.username, 'email': self.user.email, 'password': self.user.password},
            'uuid': str(self.uuid), 'balance': self.balance, 'default': self.default,
            'expired': str(self.expired) if self.expired is not None else None
        }

    @classmethod
    def get_available_balance(cls, organization):
        queryset = cls.objects.filter(organization=organization).active().filter(balance=-1)
        if queryset.exists():
            return -1
        queryset = cls.objects.filter(organization=organization).active().aggregate(total_balance=Sum('balance'))
        return queryset['total_balance']

    @classmethod
    def add_extra_key(cls, organization, license_key):
        data = cls.decode(license_key)

        site_data = data.pop('site')
        user_data = data.pop('user')
        organization_data = data.pop('organization')

        if organization.name != organization_data.get('name'):
            raise ValueError('This is invalid key.')

        instance = cls.objects.create_extra(organization=organization, **data)
        return instance

    @staticmethod
    def encode(data):
        s = json.dumps(data)
        return base64.encodestring(s)

    @staticmethod
    def decode(data):
        s = base64.decodestring(data)
        return json.loads(s)

    @property
    def is_expired(self):
        if self.expired < timezone.now():
            return True
        return False
