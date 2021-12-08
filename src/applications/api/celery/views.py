# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from celery.result import AsyncResult
from rest_framework.viewsets import ViewSet
from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import APIException

# from django_celery_results.models import TaskResult
from applications.api.celery.serializers import TaskResultSerializer


class TaskResultViewSet(ViewSet):
    # queryset = TaskResult.objects.all()
    # model = TaskResult
    serializer_class = TaskResultSerializer

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        return {
            'request': self.request,
            'format': self.format_kwarg,
            'view': self
        }

    def get_serializer(self, *args, **kwargs):
        """
        Return the serializer instance that should be used for validating and
        deserializing input, and for serializing output.
        """
        serializer_class = self.serializer_class
        kwargs['context'] = self.get_serializer_context()
        return serializer_class(*args, **kwargs)

    def retrieve(self, request, task_id, *args, **kwargs):
        try:
            instance = AsyncResult(id=task_id)
            serializer = self.get_serializer(instance)
            data = serializer.data
        except Exception as exc:
            raise APIException(detail='Something went wrong.')

        return Response(data=data, status=status.HTTP_200_OK)
