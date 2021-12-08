# -*- coding: utf-8 -*-
from urllib.parse import urlsplit

from django.conf import settings


def build_absolute_uri(organization, location, protocol=None):
    """request.build_absolute_uri() helper

    Like request.build_absolute_uri, but gracefully handling
    the case where request is None.
    """

    if organization:
        site = organization.site
        bits = urlsplit(location)
        if not (bits.scheme and bits.netloc):
            uri = '{proto}://{domain}{url}'.format(
                proto=settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL,
                domain=site.domain,
                url=location)
        else:
            uri = location
    else:
        return ''

    if not protocol and settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL == 'https':
        protocol = settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL

    if protocol:
        uri = protocol + ':' + uri.partition(':')[2]
    return uri
