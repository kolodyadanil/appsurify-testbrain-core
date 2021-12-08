# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.template.defaultfilters import slugify
from django.db.models import Q
from django.contrib.sites.models import Site
from django.conf import settings


from applications.organization.utils import default_org_model


class CheckCompanyName(APIView):
    permission_classes = (AllowAny,)

    def get(self, request, *args, **kwargs):
        company_name = request.query_params.get('company_name', None)
        slug = slugify(company_name)
        base_domain = settings.BASE_ORG_DOMAIN

        site_domain = '{}.{}'.format(slug, base_domain)

        OrganizationModel = default_org_model()

        organization = OrganizationModel.objects.filter(Q(name=company_name) | Q(slug=slug))

        if organization or not company_name or not slug:
            return Response({'exists': True, 'slug': site_domain}, status=status.HTTP_200_OK)

        return Response({'exists': False, 'slug': site_domain}, status=status.HTTP_200_OK)


check_company_name_view = CheckCompanyName.as_view()
