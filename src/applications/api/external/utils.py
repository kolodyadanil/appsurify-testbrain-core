# -*- coding: utf-8 -*-
from django.conf import settings
from django.core import signing

from applications.organization.models import Organization


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
            pk = signing.Signer(salt=settings.TOKEN_SALT).unsign(signing.b64_decode(key))
            ret = Organization.objects.get(pk=pk)
        except (signing.BadSignature, Organization.DoesNotExist):
            ret = None
        return ret
