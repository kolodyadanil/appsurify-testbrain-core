# -*- coding: utf-8 -*-

import requests
import tempfile
from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseServerError, HttpResponse
from django.utils.encoding import force_bytes
from hashlib import sha1, sha256
from hmac import HMAC, compare_digest

from applications.allauth.account.utils import user_username, user_email, user_field
from applications.allauth.utils import valid_email_or_none


def upload_github_avatar(url):
    response = requests.get(url, stream=True)
    if response.status_code != requests.codes.ok:
        return None

    temp = tempfile.NamedTemporaryFile()

    for block in response.iter_content(1024 * 8):
        if not block:
            return None

        temp.write(block)

    return temp


def verify_secret_hook(request, context):
    received_sign = request.META.get('HTTP_X_HUB_SIGNATURE_256', 'sha256=').split('sha256=')[-1].strip()
    if not received_sign:
        return False, 'Signature not found'

    data = context.get('body')

    secret = settings.SECRET_KEYS.get('GITHUB')
    expected_sign = HMAC(key=secret, msg=data, digestmod=sha256).hexdigest()

    accept_result = compare_digest(received_sign, expected_sign)
    if not accept_result:
        return False, 'Permission denied'
    return True, 'OK'


def populate_user(user, data):
    username = data.get('login')
    email = data.get('email')
    name = data.get('name')
    user_username(user, username or '')
    user_email(user, valid_email_or_none(email) or '')
    name_parts = (name or '').partition(' ')
    user_field(user, 'first_name', name_parts[0])
    user_field(user, 'last_name', name_parts[2])
    return user
