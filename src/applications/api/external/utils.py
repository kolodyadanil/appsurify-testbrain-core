# -*- coding: utf-8 -*-
from django.conf import settings
from django.core import signing

from applications.organization.models import Organization
import sys

_ver = sys.version_info

#: Python 2.x?
is_py2 = (_ver[0] == 2)

#: Python 3.x?
is_py3 = (_ver[0] == 3)

class ConfirmationHMAC(object):
    def __init__(self, organization):
        self.organization = organization

    @property
    def key(self):
        payload = bytes(signing.Signer(salt=settings.TOKEN_SALT).sign(value=self.organization.pk), "utf-8")
        key = signing.b64_encode(payload)
        return key

    @classmethod
    def from_key(cls, key):
        try:
            if is_py2:
                pk = signing.Signer(salt=settings.TOKEN_SALT).unsign(signing.b64_decode(key))
            else:
                key = key.encode()
                pk = signing.Signer(salt=settings.TOKEN_SALT).unsign(signing.b64_decode(key).decode('utf-8'))
            ret = Organization.objects.get(pk=pk)
        except (signing.BadSignature, Organization.DoesNotExist):
            ret = None
        return ret
