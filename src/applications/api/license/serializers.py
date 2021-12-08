# -*- coding: utf-8 -*-
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site
from django.conf import settings
from django.db import transaction
from django.http import HttpRequest
from django.template.defaultfilters import slugify

from rest_framework import serializers, exceptions
from rest_framework.authtoken.models import Token

from applications.allauth.account.utils import sync_user_email_addresses
from applications.allauth.utils import email_address_exists
from applications.allauth.account.adapter import get_adapter
from applications.api.external.utils import ConfirmationHMAC
from applications.organization.models import Organization
from applications.organization.utils import create_organization, get_current_organization, check_company_name, create_organization_from_key
from applications.license.models import LicenseKey


class LicenseKeySerializer(serializers.ModelSerializer):

    class Meta(object):
        model = LicenseKey
        fields = '__all__'
