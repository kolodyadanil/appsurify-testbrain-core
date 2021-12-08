# -*- coding: utf-8 -*-
from system.env import env


# ALL AUTH
# ------------------------------------------------------------------------------
LOGIN_REDIRECT_URL = '/home'
ACCOUNT_EMAIL_SUBJECT_PREFIX = ''
ACCOUNT_DEFAULT_HTTP_PROTOCOL = env('ACCOUNT_DEFAULT_HTTP_PROTOCOL', default='http')
ACCOUNT_AUTHENTICATION_METHOD = 'username_email'
ACCOUNT_AUTHENTICATED_LOGIN_REDIRECTS = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
ACCOUNT_LOGIN_ATTEMPTS_LIMIT = 5
ACCOUNT_LOGIN_ATTEMPTS_TIMEOUT = 300
ACCOUNT_LOGIN_ON_SIGNUP = False
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = True
ACCOUNT_LOGOUT_REDIRECT_URL = '/login'
ACCOUNT_SIGNUP_IS_OPEN = False
ACCOUNT_SIGNUP_EMAIL_ENTER_TWICE = False
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 7
ACCOUNT_EMAIL_CONFIRMATION_HMAC = False
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = '/home'
ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = '/login'
ACCOUNT_USER_MODEL_EMAIL_FIELD = 'email'
ACCOUNT_USER_MODEL_USERNAME_FIELD = 'username'
ACCOUNT_PASSWORD_MIN_LENGTH = 0
ACCOUNT_PASSWORD_RESET_TIMEOUT_DAYS = 7
ACCOUNT_PASSWORD_CHANGE_REDIRECT_URL = '/profile/password/set'
SOCIALACCOUNT_REDIRECT_URL = '/profile'
SOCIALACCOUNT_QUERY_EMAIL = True
TOKEN_SALT = 'salt'
TOKEN_EXPIRE_DAYS = 7

SOCIALACCOUNT_PROVIDERS = {
    'github': {
        'SCOPE': [
            'read:user',
            'user:email',
            'read:org',
            'repo',
        ],
    },
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    },
    'bitbucket': {
        'SCOPE': [
            'account',
            'repository',
        ],
    }
}