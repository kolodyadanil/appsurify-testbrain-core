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
# from applications.license.models import LicenseKey


class CreateOrganizationSerializer(serializers.Serializer):
    company_name = serializers.CharField(required=True, write_only=True)
    email = serializers.EmailField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, required=True)
    api_token = serializers.SerializerMethodField()
    user_token = serializers.SerializerMethodField()

    def get_api_token(self, obj):
        request = self._get_request()
        organization = get_current_organization(request=request)
        return ConfirmationHMAC(organization).key

    def get_user_token(self, obj):
        return obj.auth_token.key

    def _get_request(self):
        request = self.context.get('request')
        if not isinstance(request, HttpRequest):
            request = request._request
        return request

    def validate_email(self, value):
        # exists = email_address_exists(value)
        # if exists:
        #     raise exceptions.ValidationError('A user is already registered with this e-mail address.')
        return value

    def validate(self, attrs):
        attrs['password1'] = attrs['password']
        attrs['password2'] = attrs['password']
        return attrs

    def create(self, validated_data):
        request = self._get_request()

        if get_current_organization(request=request):
            raise exceptions.ValidationError('Organization already exist.')

        try:
            site = get_current_site(request=request)
        except Site.DoesNotExist:
            raise exceptions.ValidationError('Domain does not exist')

        company_name = validated_data.get('company_name')
        email = validated_data.get('email')

        with transaction.atomic():
            adapter = get_adapter()

            if email_address_exists(email):
                user = get_user_model().objects.get(email=email)
            else:
                user = adapter.new_user(request)
                adapter.save_user(request, user, self.validated_data, commit=True)
                sync_user_email_addresses(user, force=True)

            token, _ = Token.objects.get_or_create(user=user)

            slug = slugify(company_name)
            create_organization(user, company_name, slug=slug, is_active=True,
                                org_defaults={'site': site}, org_user_defaults={'is_admin': True})

            # if getattr(settings, 'SITE_ID', False):
            #     for project in organization.projects.all():
            #         project.get_or_add_user(user=user)

            return user


class OrganizationSerializer(serializers.ModelSerializer):

    api_token = serializers.SerializerMethodField()

    class Meta(object):
        model = Organization
        fields = ['id', 'name', 'site', 'api_token', ]

    def _get_request(self):
        request = self.context.get('request')
        if not isinstance(request, HttpRequest):
            request = request._request
        return request

    def get_api_token(self, obj):
        request = self._get_request()
        organization = get_current_organization(request=request)
        return ConfirmationHMAC(organization).key


class LicenseInitSerializer(serializers.Serializer):
    license_key = serializers.CharField(write_only=True, required=True)

    api_token = serializers.SerializerMethodField()
    user_token = serializers.SerializerMethodField()

    def get_api_token(self, obj):
        request = self._get_request()
        organization = get_current_organization(request=request)
        return ConfirmationHMAC(organization).key

    def get_user_token(self, obj):
        return obj.auth_token.key

    def _get_request(self):
        request = self.context.get('request')
        if not isinstance(request, HttpRequest):
            request = request._request
        return request

    def validate_license_key(self, value):
        try:
            # LicenseKey.decode(value)
            return value
        except Exception as e:
            raise serializers.ValidationError(e.message)

    def validate(self, attrs):
        return attrs

    def create(self, validated_data):
        # request = self._get_request()
        #
        # if get_current_organization(request=request):
        #     raise serializers.ValidationError('Organization already exist. Use add extra key.')
        #
        # try:
        #     organization = create_organization_from_key(license_key=validated_data.get('license_key'), request=request)
        # except Exception as e:
        #     raise serializers.ValidationError(e.message)
        #
        # return organization.owner.organization_user.user
        raise serializers.ValidationError("Not implemented")


class LicenseAddSerializer(serializers.Serializer):

    license_key = serializers.CharField(write_only=True, required=True)

    def _get_request(self):
        request = self.context.get('request')
        if not isinstance(request, HttpRequest):
            request = request._request
        return request

    def validate_license_key(self, value):
        try:
            # LicenseKey.decode(value)
            return value
        except Exception as e:
            raise serializers.ValidationError('Incorrect license key')

    def validate(self, attrs):
        return attrs

    def create(self, validated_data):
        # request = self._get_request()
        #
        # organization = get_current_organization(request=request)
        # if not organization:
        #     raise serializers.ValidationError('Init organization first.')
        #
        # try:
        #     license_key = LicenseKey.add_extra_key(organization=organization,
        #                                            license_key=validated_data.get('license_key'))
        #     return license_key
        # except ValueError:
        #     raise serializers.ValidationError('This license key already added.')
        # except Exception as e:
        #     raise serializers.ValidationError(e.message)
        raise serializers.ValidationError("Not implemented")
