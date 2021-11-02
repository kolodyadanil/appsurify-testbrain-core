# -*- coding: utf-8 -*-
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

from applications.customers.shortcuts import get_current_organization


class OrganizationMiddleware(MiddlewareMixin):
    """
    Middleware that sets `organization` attribute to request object.
    """
    def process_request(self, request):
        request.organization = get_current_organization(request=request)
