# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rest_framework.permissions import BasePermission

from applications.api.external.utils import ConfirmationHMAC


class IsAuthenticatedToken(BasePermission):
    def has_permission(self, request, view):
        token = request.META.get('HTTP_TOKEN', None)
        if token:
            user = ConfirmationHMAC.from_key(token)
        else:
            user = None
        return user
