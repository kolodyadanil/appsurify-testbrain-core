# -*- coding: utf-8 -*-
from __future__ import unicode_literals


from rest_framework import generics


class OrganizationModelViewSet(generics.GenericAPIView):

    def get_queryset(self):
        pass
