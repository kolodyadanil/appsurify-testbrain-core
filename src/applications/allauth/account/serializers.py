# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import time
from enum import Enum
from django.core.exceptions import ValidationError

from django.db.transaction import atomic
from drf_yasg.utils import swagger_serializer_method

from applications.organization.models import Organization, OrganizationUser
from applications.api.external.utils import ConfirmationHMAC

try:
    from applications.allauth.account import app_settings as allauth_settings
    from applications.allauth.utils import (
        email_address_exists,
        get_username_max_length,
        send_registration_email
    )
    from applications.allauth.account.adapter import get_adapter
    from applications.allauth.account.utils import setup_user_email, filter_users_by_email
except ImportError:
    raise ImportError("allauth needs to be added to INSTALLED_APPS.")

from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from requests.exceptions import HTTPError
from django.contrib.auth import get_user_model, authenticate
from applications.allauth.socialaccount.models import SocialAccount
from rest_framework import serializers, exceptions
from applications.allauth.socialaccount.helpers import complete_social_login
from applications.project.models import Project
from collections import OrderedDict
from applications.organization.utils import (
    create_organization,
    check_company_name,
    get_current_organization
)
from django.contrib.sites.shortcuts import get_current_site
from .app_settings import AuthenticationMethod
from . import app_settings
from .exceptions import UnableLoginError
from ..compat import reverse
from ..utils import (
    build_absolute_uri,
    get_username_max_length,
    set_form_field_order,
)
from .utils import (
    filter_users_by_email,
    get_user_model,
    perform_login,
    setup_user_email,
    url_str_to_user_pk,
    user_email,
    user_pk_to_url_str,
    user_username,
)
from django.contrib.auth import password_validation
from django.http import HttpRequest
from django.contrib.sites.models import Site
from django.template.defaultfilters import slugify
from applications.allauth.socialaccount.models import SocialApp

from django.utils.translation import gettext_lazy as _


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that takes an additional `fields` argument that
    controls which fields should be displayed.
    """

    def __init__(self, *args, **kwargs):
        fields = None

        if fields is None:
            # Don't pass the 'fields' arg up to the superclass
            fields = kwargs.pop('fields', None)

        super(DynamicFieldsModelSerializer, self).__init__(*args, **kwargs)

        if 'request' in self.context:
            try:
                fields = self.context['request'].query_params.get('fields', None)
            except AttributeError:
                fields = None

        if fields is not None:
            if not isinstance(fields, (list, tuple)):
                fields = fields.split(',')

            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields.keys())
            for field_name in existing - allowed:
                self.fields.pop(field_name)


class BaseRelatedSerializer(serializers.RelatedField):
    fields = '__all__'
    pk_name = 'id'

    def __init__(self, **kwargs):
        self.fields = kwargs.pop('fields', '__all__')
        self.pk_name = kwargs.pop('pk_name', 'id')
        self.pk_field = kwargs.pop('pk_field', None)
        super(BaseRelatedSerializer, self).__init__(**kwargs)

    @property
    def _meta(self):
        return self.Meta

    def to_internal_value(self, data):
        if self.pk_field is not None:
            data = self.pk_field.to_internal_value(data)

        try:
            if isinstance(data, dict) and self.pk_name in data:
                data = self.get_queryset().get(pk=data[self.pk_name])
            else:
                data = self.get_queryset().get(pk=data)
            return data
        except ObjectDoesNotExist:
            self.fail('does_not_exist', pk_value=data)
        except (TypeError, ValueError):
            self.fail('incorrect_type', data_type=type(data).__name__)

    def to_representation(self, value, force_pk_only=False):
        if self.pk_field is not None:
            return self.pk_field.to_representation(value.pk)
        if not self.use_pk_only_optimization() and not isinstance(value, bool) and not force_pk_only:
            serializer = self._meta.model_serializer_class
            value = serializer(value, fields=self.fields, read_only=True).data
        elif self.use_pk_only_optimization() or force_pk_only:
            value = getattr(value, self.pk_name)
        else:
            value = value
        return value

    def get_choices(self, cutoff=None):
        queryset = self.get_queryset()
        if queryset is None:
            # Ensure that field.choices returns something sensible
            return {}

        if cutoff is not None:
            queryset = queryset[:cutoff]

        return OrderedDict([
            (
                self.to_representation(item, force_pk_only=True),
                self.display_value(item)
            )
            for item in queryset
        ])


class TokenSerializer(serializers.ModelSerializer):
    """
    Serializer for Token model.
    """

    class Meta(object):
        model = Token
        fields = ('key',)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(style={'input_type': 'password'})

    def _validate_email(self, email, password):
        user = None
        request = self.context['request']
        if email and password:
            user = authenticate(request=request, email=email, password=password)
        else:
            msg = 'Must include "email" and "password".'
            raise exceptions.ValidationError(msg)

        return user

    def _validate_username(self, username, password):
        user = None
        request = self.context['request']

        if username and password:
            user = authenticate(request=request, username=username, password=password)
        else:
            msg = 'Must include "username" and "password".'
            raise exceptions.ValidationError(msg)

        return user

    def _validate_username_email(self, username, email, password):
        user = None
        request = self.context['request']

        if email and password:
            user = authenticate(request=request, email=email, password=password)
        elif username and password:
            user = authenticate(request=request, username=username, password=password)
        else:
            msg = 'Must include either "username" or "email" and "password".'
            raise exceptions.ValidationError(msg)

        return user

    def validate(self, attrs):
        username = attrs.get('username')
        email = attrs.get('email')
        password = attrs.get('password')

        user = None

        from . import app_settings

        # Authentication through email
        if app_settings.AUTHENTICATION_METHOD == app_settings.AuthenticationMethod.EMAIL:
            user = self._validate_email(email, password)

        # Authentication through username
        if app_settings.AUTHENTICATION_METHOD == app_settings.AuthenticationMethod.USERNAME:
            user = self._validate_username(username, password)

        # Authentication through either username or email
        else:
            user = self._validate_username_email(username, email, password)

        # Did we get back an active user?
        if user:
            if not user.is_active:
                msg = 'User account is disabled.'
                raise exceptions.ValidationError(msg)
        else:
            msg = 'Unable to log in with provided credentials.'
            raise UnableLoginError(msg)

        # If required, is the email verified?

        if not user.is_superuser:
            from . import app_settings

            if app_settings.EMAIL_VERIFICATION == app_settings.EmailVerificationMethod.MANDATORY:

                email_address = user.emailaddress_set.get(email=user.email)

                if not email_address.verified:
                    raise serializers.ValidationError('E-mail is not verified.')

        attrs['user'] = user

        return attrs


class OrganizationSignupSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=get_username_max_length(),
                                     min_length=allauth_settings.USERNAME_MIN_LENGTH,
                                     required=allauth_settings.USERNAME_REQUIRED)
    first_name = serializers.CharField(min_length=2, max_length=26, required=True)
    last_name = serializers.CharField(min_length=2, max_length=26, required=True)

    email = serializers.EmailField(required=allauth_settings.EMAIL_REQUIRED)
    email2 = serializers.EmailField(write_only=True, required=False)

    password1 = serializers.CharField(write_only=True, required=False)
    password2 = serializers.CharField(write_only=True, required=False)

    company_name = serializers.CharField(write_only=True, required=False)
    token = serializers.CharField(write_only=True, required=False)

    def _validate_unique_email(self, email):
        return get_adapter().validate_unique_email(email)

    def _validate_username(self, username):
        username = get_adapter().clean_username(username)
        return username

    def _validate_email(self, email):
        email = get_adapter().clean_email(email)
        return email

    def _validate_password1(self, password):
        return get_adapter().clean_password(password)

    def _validate_organization_name(self, organization_name):
        if check_company_name(organization_name):
            msg = 'Organization already exist.'
            raise exceptions.ValidationError(msg)
        return organization_name

    def _validate_organization_domain(self, organization_name):
        slug = slugify(organization_name)
        base_domain = settings.BASE_ORG_DOMAIN
        site_domain = '{}.{}'.format(slug, base_domain)
        if Site.objects.filter(domain=site_domain).exists():
            msg = 'Organization domain already exist.'
            raise exceptions.ValidationError(msg)
        return site_domain

    def validate(self, attrs: OrderedDict):
        username_attr = attrs.get('username')
        if username_attr:
            self._validate_username(username_attr)

        email = self._validate_email(attrs.get('email'))
        self._validate_organization_name(attrs.get('company_name'))

        site_domain = self._validate_organization_domain(attrs.get('company_name'))
        attrs['company_domain'] = site_domain

        if allauth_settings.UNIQUE_EMAIL:
            try:
                email = self._validate_unique_email(email)
            except ValidationError as e:
                raise serializers.ValidationError({'email': e})

        if allauth_settings.SIGNUP_EMAIL_ENTER_TWICE:
            if 'email2' not in attrs:
                raise serializers.ValidationError({'email': 'The email fields didn\'t match.'})

            email2 = self._validate_email(attrs.get('email2'))
            if (email and email2) and email != email2:
                raise serializers.ValidationError('You must type the same email each time.')

        password = attrs.get('password1')
        if password:
            try:
                get_adapter().clean_password(password, user=None)
            except ValidationError as e:
                raise serializers.ValidationError({'password': e})
            if allauth_settings.SIGNUP_PASSWORD_ENTER_TWICE:
                if 'password2' not in attrs:
                    raise serializers.ValidationError({'password': 'The password fields didn\'t match.'})

                password2 = attrs.get('password2')
                if (password and password2) and password != password2:
                    raise serializers.ValidationError('You must type the same password each time.')

        return attrs

    def custom_signup(self, request, organization, user):
        # print request.scheme
        # print request.is_secure()
        # token = self.validated_data['token']
        # if token:
        #     customer, created = Customer.get_or_create(subscriber=user)
        #     card = customer.add_card(token)
        #
        #     if not card:
        #         return False
        #     plan = Plan.objects.last()
        #     if plan:
        #         customer.subscribe(plan)

        for social_app in SocialApp.objects.all():
            social_app.sites.add(organization.site)

        send_registration_email(organization, user, proto=request.scheme)

    def save(self, request):
        adapter = get_adapter()

        company_name = self.validated_data['company_name']
        company_domain = self.validated_data['company_domain']

        # token = self.validated_data['token']

        with atomic():
            user = adapter.new_user(request)
            adapter.save_user(request, user, self.validated_data, commit=True)
            # Temporarily allow for optional email verification
            setup_user_email(request, user, [], email_verified=True)

            site = Site.objects.create(domain=company_domain, name=company_domain)
            organization = create_organization(user, company_name, slug=slugify(company_name), is_active=True,
                                               org_defaults={'site': site}, org_user_defaults={'is_admin': True})

            self.custom_signup(request, organization, user)

            return organization


class OrganizationSignupV2Serializer(serializers.Serializer):
    email = serializers.EmailField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, required=True)

    hostname = serializers.SerializerMethodField()

    _blacklist_domains = []

    def get_hostname(self, obj):
        return obj.site.domain

    def _get_request(self):
        request = self.context.get('request')
        if not isinstance(request, HttpRequest):
            request = request._request
        return request

    def validate_email(self, value):
        User = get_user_model()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('This email already exists.')
        return value

    def validate_password(self, value):
        try:
            password_validation.validate_password(value, user=None)
        except ValidationError as e:
            message = e.messages
            if isinstance(message, list):
                message = '\n'.join(e.messages)
            raise serializers.ValidationError(message)
        return value

    def validate(self, attrs):
        return attrs

    def create(self, validated_data):
        from applications.organization.utils import create_organization_from_credentials

        with atomic():
            organization = create_organization_from_credentials(
                email=validated_data['email'], password=validated_data['password'], request=self._get_request())

            for social_app in SocialApp.objects.all():
                social_app.sites.add(organization.site)

            return organization


class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=get_username_max_length(),
                                     min_length=allauth_settings.USERNAME_MIN_LENGTH,
                                     required=allauth_settings.USERNAME_REQUIRED)

    email = serializers.EmailField(required=allauth_settings.EMAIL_REQUIRED)
    email2 = serializers.EmailField(write_only=True, required=False)

    password1 = serializers.CharField(write_only=True, required=False)
    password2 = serializers.CharField(write_only=True, required=False)

    company_name = serializers.CharField(write_only=True, required=False)
    token = serializers.CharField(write_only=True, required=True)

    def _validate_unique_email(self, email):
        return get_adapter().validate_unique_email(email)

    def _validate_username(self, username):
        username = get_adapter().clean_username(username)
        return username

    def _validate_email(self, email):
        email = get_adapter().clean_email(email)
        return email

    def _validate_password1(self, password):
        return get_adapter().clean_password(password)

    def validate(self, attrs):
        # adapter = get_adapter()
        # attrs['user'] = adapter.new_user(self.context['request'])

        username = self._validate_username(attrs.get('username'))
        email = self._validate_email(attrs.get('email'))

        if allauth_settings.UNIQUE_EMAIL:
            try:
                email = self._validate_unique_email(email)
            except ValidationError as e:
                raise serializers.ValidationError({'email': e})

        if allauth_settings.SIGNUP_EMAIL_ENTER_TWICE:
            if 'email2' not in attrs:
                raise serializers.ValidationError({'email': 'The email fields didn\'t match.'})

            email2 = self._validate_email(attrs.get('email2'))
            if (email and email2) and email != email2:
                raise serializers.ValidationError('You must type the same email each time.')

        password = attrs.get('password1')
        if password:
            try:
                get_adapter().clean_password(password, user=None)
            except ValidationError as e:
                raise serializers.ValidationError({'password': e})
            if allauth_settings.SIGNUP_PASSWORD_ENTER_TWICE:
                if 'password2' not in attrs:
                    raise serializers.ValidationError({'password': 'The password fields didn\'t match.'})

                password2 = attrs.get('password2')
                if (password and password2) and password != password2:
                    raise serializers.ValidationError('You must type the same password each time.')

        return attrs

    def custom_signup(self, request, user):
        pass

    def save(self, request):
        adapter = get_adapter()

        company_name = request.data.get('company_name')

        token = request.data.get('token')

        if check_company_name(company_name):
            return False

        with atomic():
            user = adapter.new_user(request)
            adapter.save_user(request, user, self.validated_data, commit=True)
            self.custom_signup(request, user)
            # setup_user_email(request, user, [])

            # customer, created = Customer.get_or_create(subscriber=user)
            # card = customer.add_card(token)

            # if not card:
            #     return False
            #
            # plan = Plan.objects.last()
            #
            # if plan:
            #     customer.subscribe(plan)

            slug = slugify(company_name)

            base_domain = settings.BASE_ORG_DOMAIN
            site_domain = '{}.{}'.format(slug, base_domain)

            site = Site.objects.create(domain=site_domain, name=site_domain)
            organization = create_organization(user, company_name, slug=slug, is_active=True,
                                               org_defaults={'site': site}, org_user_defaults={'is_admin': True})

            if organization:
                for social_app in SocialApp.objects.all():
                    social_app.sites.add(site)

            send_registration_email(email=user.email, username=user.username, company_domain=site_domain)

            return user


class InviteSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True, write_only=True)
    is_admin = serializers.BooleanField(required=False, write_only=True, default=False)

    def _validate_unique_email(self, email):
        return get_adapter().validate_unique_email(email)

    def _validate_email(self, email):
        email = get_adapter().clean_email(email)
        return email

    def _validate_organization_member(self, organization, user):
        return organization.is_member(user)

    def _validate_project_member(self, project, user):
        return project.is_member(user)

    def validate(self, attrs):
        attrs['email'] = self._validate_email(attrs.get('email'))
        return attrs

    def custom_signup(self, request, user):
        pass

    def save(self, request):
        adapter = get_adapter()

        email = self.validated_data.get('email')
        is_admin = self.validated_data.get('is_admin', False)

        if not email_address_exists(email):
            user = adapter.new_user(request)
            adapter.save_user(request, user, self.validated_data)
            setup_user_email(request, user, [])

        user = adapter.get_user(request, email)

        organization = get_current_organization(request)

        if organization is None:
            raise exceptions.NotFound('Organization not found!')

        if not self._validate_organization_member(organization, user):
            organization.add_user(user, is_admin=is_admin)

        return user


class PasswordSetSerializer(serializers.Serializer):
    password1 = serializers.CharField(write_only=True, required=False)
    password2 = serializers.CharField(write_only=True, required=False)

    def _validate_password1(self, password):
        return get_adapter().clean_password(password)

    def validate(self, attrs):
        password = attrs.get('password1')
        if password:
            try:
                get_adapter().clean_password(password, user=None)
            except ValidationError as e:
                raise serializers.ValidationError({'password': e})

            password2 = attrs.get('password2')
            if (password and password2) and password != password2:
                raise serializers.ValidationError('You must type the same password each time.')
        return attrs

    def save(self, request):
        adapter = get_adapter()
        user = request.user
        adapter.set_password(user, self.validated_data['password1'])
        return user


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def _validate_email(self, email):
        email = get_adapter().clean_email(email)
        self.users = filter_users_by_email(email)
        if not self.users:
            raise serializers.ValidationError({'email': 'The e-mail address is not assigned to any user account'})
        return email

    def validate(self, attrs):
        email = self._validate_email(attrs.get('email'))
        attrs['email'] = email
        return attrs

    def save(self, request, **kwargs):
        current_organization = get_current_organization(request)
        current_site = get_current_site(request)
        email = self.validated_data['email']
        token_generator = kwargs.get('token_generator', default_token_generator)

        for user in self.users:

            temp_key = token_generator.make_token(user)
            # save it to the password reset model
            # password_reset = PasswordReset(user=user, temp_key=temp_key)
            # password_reset.save()

            # send the password reset email
            path = reverse("account_reset_password_from_key",
                           kwargs=dict(uidb36=user_pk_to_url_str(user), key=temp_key))
            url = build_absolute_uri(request, path)

            context = {"current_site": current_site,
                       "site_name": current_site.name,
                       "user": user,
                       "password_reset_url": url,
                       "request": request
                       }

            if app_settings.AUTHENTICATION_METHOD \
                    != AuthenticationMethod.EMAIL:
                context['username'] = user_username(user)
            get_adapter(request).send_mail('account/email/password_reset_key', email, context)
        return email


class PasswordResetConfirmSerializer(serializers.Serializer):
    uidb36 = serializers.CharField()
    key = serializers.CharField()

    reset_user = None
    token_generator = default_token_generator

    error_messages = {
        'token_invalid': 'The password reset token was invalid.'
    }

    # def _get_user(self, uidb36):
    #     User = get_user_model()
    #     try:
    #         pk = url_str_to_user_pk(uidb36)
    #         return User.objects.get(pk=pk)
    #     except (ValueError, User.DoesNotExist):
    #         return None

    # def clean(self):
    #     cleaned_data = super(UserTokenForm, self).clean()
    #
    #     uidb36 = cleaned_data['uidb36']
    #     key = cleaned_data['key']
    #
    #     self.reset_user = self._get_user(uidb36)
    #     if (self.reset_user is None or
    #             not self.token_generator.check_token(self.reset_user, key)):
    #         raise forms.ValidationError(self.error_messages['token_invalid'])
    #
    #     return cleaned_data


class UserDetailsSerializer(serializers.ModelSerializer):
    """
    User model w/o password
    """

    class Meta(object):
        model = get_user_model()
        fields = ('pk', 'username', 'email', 'first_name', 'last_name')
        read_only_fields = ('email',)


class SubcriptionPlan(str, Enum):
    FREE_TRIAL = "FREE_TRIAL"
    FREE = "FREE"
    PLUS = "PLUS"
    PROFESSIONAL = "PROFESSIONAL"

org_subcription_plan = [e.value for e in SubcriptionPlan]


class SubscriptionSerializer(serializers.Serializer):
    paid_until = serializers.IntegerField()
    active = serializers.BooleanField()
    current_plan = serializers.ChoiceField(choices=org_subcription_plan)
    time_saving_left = serializers.IntegerField()


class UserSerializer(DynamicFieldsModelSerializer, UserDetailsSerializer):
    social_accounts = serializers.SerializerMethodField()

    is_org_owner = serializers.SerializerMethodField(source='get_is_org_owner')
    is_org_admin = serializers.SerializerMethodField(source='get_is_org_admin')
    api_key = serializers.SerializerMethodField(source='get_api_key')

    interface_type = serializers.SerializerMethodField(source='get_interface_type')
    subscription = serializers.SerializerMethodField()

    class Meta(object):
        model = get_user_model()
        fields = ('id', 'username', 'email', 'first_name', 'last_name',
                  'social_accounts', 'is_org_owner', 'is_org_admin', 'api_key', 'interface_type', "subscription",)
        read_only_fields = ('email',)

    @swagger_serializer_method(serializer_or_field=SubscriptionSerializer)
    def get_subscription(self, user):
        organizations = Organization.objects.all()
        paid_until = 0
        for organization in organizations:
            if organization.users.filter(email=user.email):
                paid_until = organization.subscription_paid_until if organization.subscription_paid_until else 0
                current_plan = organization.plan
                time_saving_left = organization.time_saving_left
                break

        active = True if paid_until > int(time.time()) else False
        subscription = dict({"paid_until": paid_until, 
                             "active": active, 
                             "current_plan": current_plan,
                             "time_saving_left": time_saving_left,})
        return subscription

    def get_interface_type(self, user):
        request = self.context['request']
        try:
            organization = get_current_organization(request=request)
            org_type = organization.type
            org_deploy_type = organization.TYPE_CLOUD

            if hasattr(settings, 'SITE_ID'):
                org_deploy_type = organization.TYPE_STANDALONE

            ret = 'full'
            if org_type == organization.TYPE_STANDALONE and org_deploy_type == organization.TYPE_CLOUD:
                ret = 'dashboard'
        except Exception as exc:
            ret = 'full'
        return ret

    def get_api_key(self, user):
        request = self.context['request']
        try:
            organization = get_current_organization(request=request)
            return ConfirmationHMAC(organization).key
        except AttributeError:
            return ''

    def get_social_accounts(self, user):
        account_data = []
        for account in SocialAccount.objects.filter(user=user):
            provider_account = account.get_provider_account()
            account_data.append({
                'id': account.pk,
                'provider': account.provider,
                'name': provider_account.to_str(),
                'profile_url': account.get_profile_url(),
                'avatar_url': account.get_avatar_url()

            })
        return account_data

    def get_is_org_owner(self, user):
        if user.is_superuser:
            return True
        request = self.context['request']
        organization = get_current_organization(request=request)
        if organization:
            return organization.is_owner(user)
        return False

    def get_is_org_admin(self, user):
        if user.is_superuser:
            return True
        request = self.context['request']
        organization = get_current_organization(request=request)
        if organization:
            return organization.is_admin(user)
        return False

    def update(self, instance, validated_data):
        super(UserSerializer, self).update(instance, validated_data)
        is_org_admin = self.initial_data.get('is_org_admin', False)
        current_organization = get_current_organization(self.context['request'])
        current_organization._org_user_model.objects.filter(user=instance).update(is_admin=is_org_admin)
        return instance


class UserRelatedSerializer(BaseRelatedSerializer):
    class Meta(object):
        model_class = get_user_model()
        model_serializer_class = UserSerializer


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField()