# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import base64
from rest_framework import HTTP_HEADER_ENCODING, exceptions
from six import text_type

from rest_framework.permissions import BasePermission
from django.conf import settings


class CLISecretTokenAuthentication(object):
    """
    Simple token based authentication.

    Clients should authenticate by passing the token key in the "Authorization"
    HTTP header, prepended with the string "Token ".  For example:

        Authorization: CLI 401f7ac837da42b97f613d789819ff93537bee6a
        CLI: 401f7ac837da42b97f613d789819ff93537bee6a

    """

    keyword = 'CLI'

    def get_authorization_header(self, request):
        """
        Return request's 'Authorization:' header, as a bytestring.

        Hide some test client ickyness where the header can be unicode.
        """
        auth = b''

        a_auth = request.META.get('HTTP_AUTHORIZATION', b'')
        c_auth = request.META.get('HTTP_CLI', b'')
        if a_auth:
            auth = a_auth
        elif c_auth:
            auth = c_auth

        if isinstance(auth, text_type):
            # Work around django test client oddness
            auth = auth.encode(HTTP_HEADER_ENCODING)
        return auth

    def authenticate(self, request):
        auth = self.get_authorization_header(request).split()

        if len(auth) > 1:
            if not auth or auth[0].lower() != self.keyword.lower().encode():
                return None

        if len(auth) == 0:
            msg = 'Invalid auth header. No credentials provided.'
            raise exceptions.ValidationError(msg)
        elif len(auth) > 2:
            msg = 'Invalid auth header. Token string should not contain spaces.'
            raise exceptions.ValidationError(msg)

        try:
            if len(auth) == 1:
                token = auth[0].decode()
            else:
                token = auth[1].decode()
        except UnicodeError:
            msg = 'Invalid auth header. Token string should not contain invalid characters.'
            raise exceptions.ValidationError(msg)

        return token

    @staticmethod
    def validate(key):
        try:
            return base64.b64decode(key) == settings.SECRET_KEY
        except TypeError:
            return False


class IsCLI(BasePermission):
    """
    Allows access only CLI request.
    """

    def has_permission(self, request, view):
        try:
            token = CLISecretTokenAuthentication().authenticate(request)
        except exceptions.ValidationError as e:
            token = ''

        return CLISecretTokenAuthentication.validate(token)