 # -*- coding: utf-8 -*-

from itertools import chain
from django.conf import settings
from django.contrib.sites.models import Site
from django.template.defaultfilters import slugify
from django.db.models import Q


def default_org_model():
    """Encapsulates importing the concrete model"""
    from applications.organization.models import Organization
    return Organization


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


def create_organization(user, name, slug=None, is_active=False, org_defaults=None, org_user_defaults=None, type=None, **kwargs):
    """
    Returns a new organization, also creating an initial organization user who
    is the owner.

    The specific models can be specified if a custom organization app is used.
    The simplest way would be to use a partial.

    >>> from organizations.utils import create_organization
    >>> from myapp.models import Account
    >>> from functools import partial
    >>> create_account = partial(create_organization, model=Account)

    """
    # from applications.license.models import LicenseKey

    org_model = kwargs.pop('model', None) or kwargs.pop('org_model', None) or default_org_model()
    kwargs.pop('org_user_model', None)  # Discard deprecated argument

    org_owner_model = org_model.owner.related.related_model
    try:
        # Django 1.9
        org_user_model = org_model.organization_users.rel.related_model
    except AttributeError:
        # Django 1.8
        org_user_model = org_model.organization_users.related.related_model

    if org_defaults is None:
        org_defaults = {}
    if org_user_defaults is None:
        if 'is_admin' in model_field_names(org_user_model):
            org_user_defaults = {'is_admin': True}
        else:
            org_user_defaults = {}

    if slug is not None:
        org_defaults.update({'slug': slug})
    if is_active is not None:
        org_defaults.update({'is_active': is_active})
    if type is not None:
        org_defaults.update({'type': type})

    org_defaults.update({'name': name})
    organization = org_model.objects.create(**org_defaults)

    org_user_defaults.update({'organization': organization, 'user': user})
    new_user = org_user_model.objects.create(**org_user_defaults)

    org_owner_model.objects.create(organization=organization, organization_user=new_user)

    # LicenseKey.objects.create_default(organization=organization)

    return organization


def model_field_attr(model, model_field, attr):
    """
    Returns the specified attribute for the specified field on the model class.
    """
    fields = dict([(field.name, field) for field in model._meta.fields])
    return getattr(fields[model_field], attr)


def get_current_organization(request):
    from django.contrib.sites.models import Site
    from django.contrib.sites.shortcuts import get_current_site

    OrganizationModel = default_org_model()

    try:
        if getattr(settings, 'ORGANIZATION_ID', ''):
            organization_id = settings.ORGANIZATION_ID
            return OrganizationModel.objects.get(id=organization_id)

        if hasattr(settings, 'SITE_ID'):
            try:
                site = Site.objects.get(id=settings.SITE_ID)
                return OrganizationModel.objects.get(site=site)
            except Site.DoesNotExist:
                site = Site.objects.last()
                return OrganizationModel.objects.get(site=site)
        else:
            site = get_current_site(request=request)
            return OrganizationModel.objects.get(site=site)
    except OrganizationModel.DoesNotExist:
        return None


def check_company_name(company_name):
    slug = slugify(company_name)
    OrganizationModel = default_org_model()

    organization = OrganizationModel.objects.filter(Q(name=company_name) | Q(slug=slug))

    if organization or not company_name or not slug:
        return True

    return False


def create_organization_from_credentials(email, password, user=None, create_license=True, request=None):
    from django.contrib.sites.shortcuts import get_current_site
    from django.contrib.auth import get_user_model
    # from applications.license.models import LicenseKey
    from applications.allauth.account.models import EmailAddress
    from rest_framework.authtoken.models import Token

    username, domain = email.split('@')

    organization_name = ''.join([str(x).capitalize() for x in domain.split('.')])
    organization_slug = slugify(organization_name)

    if user is None:
        User = get_user_model()
        user = User.objects.create_user(username=slugify(email), email=email, password=password)
        Token.objects.get_or_create(user=user)
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)

    if hasattr(settings, 'SITE_ID'):
        try:
            site = get_current_site(request=request)
            site.domain = '{}.{}'.format(organization_slug, settings.BASE_ORG_DOMAIN)
            site.name = '{}.{}'.format(organization_slug, settings.BASE_ORG_DOMAIN)
            site.save()
        except Site.DoesNotExist:
            site = Site.objects.create(
                domain='{}.{}'.format(organization_slug, settings.BASE_ORG_DOMAIN),
                name='{}.{}'.format(organization_slug, settings.BASE_ORG_DOMAIN)
            )
    else:
        site = Site.objects.create(
            domain='{}.{}'.format(organization_slug, settings.BASE_ORG_DOMAIN),
            name='{}.{}'.format(organization_slug, settings.BASE_ORG_DOMAIN)
        )

    organization = create_organization(user, organization_name, slug=organization_slug, is_active=True,
                                       org_defaults={'site': site}, org_user_defaults={'is_admin': True},
                                       type=u'standalone')
    # if create_license:
    #     _ = LicenseKey.objects.create_default(organization=organization)
    return organization


def create_organization_from_key(license_key, request=None):
    # from django.contrib.sites.shortcuts import get_current_site
    # from django.contrib.auth import get_user_model
    # from applications.license.models import LicenseKey
    # from applications.allauth.account.models import EmailAddress
    # from rest_framework.authtoken.models import Token
    #
    # OrgModel = default_org_model()
    #
    # data = LicenseKey.decode(license_key)
    #
    # if data.get('default') is False:
    #     raise ValueError('Extra license key value must have default=True.')
    #
    # if OrgModel.objects.all().count() > 0:
    #     raise ValueError('Organization already exist for this instance.')
    #
    # site_name, site_domain = data.get('site')['name'], data.get('site')['domain']
    # site = get_current_site(request=request)
    # site.domain = site_domain
    # site.name = site_name
    # site.save()
    #
    # user = get_user_model()(**data.get('user'))
    # user.save()
    #
    # Token.objects.get_or_create(user=user)
    # EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    #
    # organization_name, organization_slug = data.get('organization')['name'], data.get('organization')['slug']
    #
    # organization = create_organization(user, organization_name, slug=organization_slug, is_active=True,
    #                                    org_defaults={'site': site}, org_user_defaults={'is_admin': True},
    #                                    type=u'standalone')
    #
    # # organization.license_keys.create(
    # #     organization=organization,
    # #     user=user,
    # #     default=data.get('default'),
    # #     balance=data.get('balance'),
    # #     expired=data.get('expired'),
    # #     uuid=data.get('uuid')
    # # )
    #
    # return organization
    return None

