# -*- coding: utf-8 -*-
from __future__ import unicode_literals


class ImmediateHttpResponse(Exception):
    """
    This exception is used to interrupt the flow of processing to immediately
    return a custom HttpResponse.
    """
    def __init__(self, response):
        self.response = response
