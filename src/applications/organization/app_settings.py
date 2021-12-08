# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.contrib.auth import get_user_model
from django.conf import settings

from .utils import model_field_attr


User = get_user_model()


# ORGS_INVITATION_BACKEND = getattr(settings, 'INVITATION_BACKEND',
#         'organizations.backends.defaults.InvitationBackend')
#
# ORGS_REGISTRATION_BACKEND = getattr(settings, 'REGISTRATION_BACKEND',
#         'organizations.backends.defaults.RegistrationBackend')
