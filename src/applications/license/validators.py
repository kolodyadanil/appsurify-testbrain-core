# -*- coding: utf-8 -*-

import re
from django.core.exceptions import ValidationError
from django.core import validators
from django.utils.deconstruct import deconstructible


# @deconstructible
# class LicenseDataValidator(object):
#     """
#     A class validating the image dimensions size. Class instance get two int params: width, height,
#     this is image sizes in px.
#     Usage:
#     >>> validator = LicenseDataValidator()
#     >>> validator(value={'key': 'value'})
#     """
#     message = 'Image dimensions (width: %(width)s, height: %(height)s) is not allowed. ' \
#               'Allowed dimensions (width: %(allowed_width)s, height: %(allowed_height)s).'
#     code = 'invalid_image_dimensions'
#
#     def __init__(self, allowed_width: int, allowed_height: int, message=None, code=None):
#         self.allowed_width = allowed_width
#         self.allowed_height = allowed_height
#
#         if message is not None:
#             self.message = message
#         if code is not None:
#             self.code = code
#
#     def __call__(self, value):
#         if self.allowed_width < value.width or self.allowed_height < value.height:
#             raise ValidationError(
#                 self.message,
#                 code=self.code,
#                 params={
#                     'width': value.width,
#                     'height': value.height,
#                     'allowed_width': self.allowed_width,
#                     'allowed_height': self.allowed_height,
#                 }
#             )
#
#     def __eq__(self, other):
#         return isinstance(other, self.__class__) and \
#                self.allowed_width == other.allowed_width and \
#                self.allowed_height == other.allowed_height and \
#                self.message == other.message and \
#                self.code == other.code