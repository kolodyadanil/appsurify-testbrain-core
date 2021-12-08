# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.dispatch
from django.dispatch import receiver
from django.contrib.auth import get_user_model


User = get_user_model()


organization_user_kwargs = {'providing_args': ['user']}
organization_user_added = django.dispatch.Signal(**organization_user_kwargs)
organization_user_removed = django.dispatch.Signal(**organization_user_kwargs)

organization_owner_kwargs = {'providing_args': ['old', 'new']}
organization_owner_changed = django.dispatch.Signal(**organization_owner_kwargs)
