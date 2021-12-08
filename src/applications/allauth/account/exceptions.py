# -*- coding: utf-8 -*-

from rest_framework import exceptions, status
from rest_framework.exceptions import APIException, _get_error_details
from django.utils.translation import ugettext_lazy as _


class UnableLoginError(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('Unable to log in with provided credentials.')
    default_code = 'unable_login'

    # def __init__(self, detail=None, code=None):
    #     if detail is None:
    #         detail = self.default_detail
    #     if code is None:
    #         code = self.default_code


