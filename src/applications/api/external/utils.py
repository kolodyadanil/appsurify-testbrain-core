# -*- coding: utf-8 -*-
from django.conf import settings
from django.core import signing

from applications.organization.models import Organization


class ConfirmationHMAC(object):
    def __init__(self, organization):
        self.organization = organization

    @property
    def key(self):
        payload = signing.Signer(salt=settings.TOKEN_SALT).sign(value=self.organization.id)
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        key = signing.b64_encode(payload)
        if isinstance(key, bytes):
            key = key.decode('utf-8')
        return key

    @classmethod
    def from_key(cls, key):
        if isinstance(key, str):
            key = key.encode('utf-8')
        try:
            payload = signing.b64_decode(key)
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
            organization_id = signing.Signer(salt=settings.TOKEN_SALT).unsign(payload)
            ret = Organization.objects.get(id=organization_id)
        except (signing.BadSignature, Organization.DoesNotExist):
            ret = None
        return ret
