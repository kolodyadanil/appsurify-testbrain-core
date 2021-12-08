# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwner(BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    Assumes the model instance has an `owner` attribute.
    """

    def has_object_permission(self, request, view, obj):
        """
        Read permissions are allowed to any request, so we'll always allow GET, HEAD or OPTIONS requests.
        :param request:
        :param view:
        :param obj:
        :return: bool:
        """

        if request.user.is_superuser:
            return True

        if request.method in SAFE_METHODS:
            return True

        # Instance must have an attribute named `owner`.
        return obj.is_owner(request.user)


class IsOwnerOrReadOnly(BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    Assumes the model instance has an `owner` attribute.
    """

    def has_object_permission(self, request, view, obj):
        """
        Read permissions are allowed to any request, so we'll always allow GET, HEAD or OPTIONS requests.
        :param request:
        :param view:
        :param obj:
        :return: bool:
        """

        if request.user.is_superuser:
            return True

        if request.method in SAFE_METHODS:
            return True

        # Instance must have an attribute named `owner`.
        return obj.is_owner(request.user)


class IsAdminOrganizationOrReadOnly(BasePermission):
    """
    Object-level permission to only allow admin of an object to edit it.
    Assumes the model instance has an `is_admin` attribute.
    """

    def has_object_permission(self, request, view, obj):
        """
        Read permissions are allowed to any request, so we'll always allow GET, HEAD or OPTIONS requests.
        :param request:
        :param view:
        :param obj:
        :return: bool:
        """

        if request.user.is_superuser:
            return True

        if request.method in SAFE_METHODS:
            return True

        # Instance must have an attribute named 'organization'.
        return obj.organization.is_admin(request.user)


class IsMember(BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    Assumes the model instance has an `owner` attribute.
    """

    def has_object_permission(self, request, view, obj):
        """
        Read permissions are allowed to any request, so we'll always allow GET, HEAD or OPTIONS requests.
        :param request:
        :param view:
        :param obj:
        :return: bool:
        """

        if request.method in SAFE_METHODS:
            return True

        # Instance must have an attribute named `owner`.
        return obj.is_member(request.user)
