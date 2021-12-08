# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.http import Http404
from django.shortcuts import get_object_or_404 as _get_object_or_404
from rest_framework import viewsets

from applications.organization.utils import get_current_organization
from .filters import *
from .serializers import *


def get_object_or_404(queryset, *filter_args, **filter_kwargs):
    """
    Same as Django's standard shortcut, but make sure to also raise 404
    if the filter_kwargs don't match the required types.
    """
    try:
        return _get_object_or_404(queryset, *filter_args, **filter_kwargs)
    except (TypeError, ValueError):
        raise Http404


class NotificationModelViewSet(viewsets.ModelViewSet):
    """
        Notification view set
    """
    model = Notification
    serializer_class = NotificationSerializer
    queryset = Notification.objects.all()

    # filter_class = NotificationFilterSet

    search_fields = ("project", )
    ordering_fields = ()
    filter_fields = ()

    lookup_field = 'pk'
    lookup_url_kwarg = 'email_alerts_pk'

    def get_queryset(self):
        queryset = super(NotificationModelViewSet, self).get_queryset()
        queryset = queryset.filter(project__organization=get_current_organization(self.request)).exclude(
            period=Notification.PERIOD_ONE_OFF
        )
        return queryset
