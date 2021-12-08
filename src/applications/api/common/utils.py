# -*- coding: utf-8 -*-
from django.conf import settings


def split_levels(fields):
    first_level_fields = []
    next_level_fields = {}

    if not fields:
        return first_level_fields, next_level_fields

    if isinstance(fields, tuple):
        fields = list(fields)

    if not isinstance(fields, list):
        fields = [a.strip() for a in fields.split(",") if a.strip()]
    for e in fields:
        if "." in e:
            first_level, next_level = e.split(".", 1)
            first_level_fields.append(first_level)
            next_level_fields.setdefault(first_level, []).append(next_level)
        else:
            first_level_fields.append(e)

    first_level_fields = list(set(first_level_fields))
    return first_level_fields, next_level_fields


def get_stripe_secret_key(stripe_live_mode):
    if stripe_live_mode:
        return settings.STRIPE_LIVE_SECRET_KEY
    else:
        return settings.STRIPE_TEST_SECRET_KEY
