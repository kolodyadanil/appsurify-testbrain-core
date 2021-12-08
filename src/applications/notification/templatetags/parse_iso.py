# -*- coding: utf-8 -*-
import pytz
import datetime
from django.template import Library

register = Library()


@register.filter(expects_localtime=True)
def parse_iso(value, timezone=None):
    datetime_obj = datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=pytz.timezone('UTC'))
    if timezone:
        try:
            return pytz.timezone(timezone).normalize(datetime_obj)
        except Exception:
            pass
    return datetime_obj
