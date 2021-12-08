# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from rest_framework.permissions import BasePermission


class IsUnusablePassword(BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    Assumes the model instance has an `owner` attribute.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.

        if request.user.is_superuser:
            return True

        return not request.user.has_usable_password()

