# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.contrib.sites.models import Site
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .abstract_models import AbstractOrganization
from .abstract_models import AbstractOrganizationOwner
from .abstract_models import AbstractOrganizationUser


class Organization(AbstractOrganization):
    """
    Default Organization model.
    """
    TYPE_SAAS = u'saas'
    TYPE_ON_PREMISES = u'on-premises'

    TYPE_CHOICE = (
        (TYPE_SAAS, 'SaaS'),
        (TYPE_ON_PREMISES, 'On-Premises'),
    )

    type = models.CharField(max_length=128, default=TYPE_SAAS, choices=TYPE_CHOICE, blank=False, null=False)

    site = models.OneToOneField(Site, related_name='organization', on_delete=models.DO_NOTHING)

    class Meta(AbstractOrganization.Meta):
        abstract = False

    @property
    def deploy_type(self):
        deploy_type = self.TYPE_CLOUD
        if hasattr(settings, 'SITE_ID'):
            deploy_type = self.TYPE_ON_PREMISES
        return deploy_type


# @receiver(post_save, sender=Organization)
# def model_file_default_license(sender, instance, created, **kwargs):
#     organization = instance
#     if not organization.license_keys.filter(default=True).exists():
#         try:
#             LicenseKey.objects.create_default(organization=organization)
#         except Exception:
#             pass


class OrganizationUser(AbstractOrganizationUser):
    """
    Default OrganizationUser model.
    """
    class Meta(AbstractOrganizationUser.Meta):
        abstract = False


class OrganizationOwner(AbstractOrganizationOwner):
    """
    Default OrganizationOwner model.
    """
    class Meta(AbstractOrganizationOwner.Meta):
        abstract = False

