# -*- coding: utf-8 -*-
from typing import Optional
from django.http.request import HttpRequest
from .models import Organization


def get_current_organization(request: "HttpRequest") -> Optional[Organization]:
    """
    Get organization instance from request.
    If global settings PLATFORM == on-premises func return last organization instance
    If global settings PLATFORM == saas func get hostname and return organization instance by domain
    If any error or not organization not found func return None

    >>> from applications.customers.shortcuts import get_current_organization
    >>> get_current_organization(request=request)
    Organization object

    :param request:
    :return:
    """
    return Organization.objects._get_organization_by_request(request=request)
