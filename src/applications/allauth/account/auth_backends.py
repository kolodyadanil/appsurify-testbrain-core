# -*- coding: utf-8 -*-
from django.contrib.auth.backends import ModelBackend

from . import app_settings
from ..utils import get_user_model
from .app_settings import AuthenticationMethod
from .utils import filter_users_by_email, filter_users_by_username
from applications.organization.utils import get_current_organization


class AuthenticationBackend(ModelBackend):

    def authenticate(self, request, **credentials):
        ret = None  # super(AuthenticationBackend, self).authenticate(**credentials)
        if app_settings.AUTHENTICATION_METHOD == AuthenticationMethod.EMAIL:
            ret = self._authenticate_by_email(request, **credentials)
        elif app_settings.AUTHENTICATION_METHOD == AuthenticationMethod.USERNAME_EMAIL:
            ret = self._authenticate_by_email(request, **credentials)
            if not ret:
                ret = self._authenticate_by_username(request, **credentials)
        else:
            ret = self._authenticate_by_username(**credentials)
        return ret

    def _authenticate_by_username(self, request=None, **credentials):
        username_field = app_settings.USER_MODEL_USERNAME_FIELD

        username = credentials.get('username')
        password = credentials.get('password')

        User = get_user_model()
        if not username_field or username is None or password is None:
            return None
        try:
            # Username query is case insensitive
            user = filter_users_by_username(username).get()

            if user.is_superuser:
                if user.check_password(password):
                    return user

            is_member = self.organization_member(request, user)
            if is_member:
                if user.check_password(password):
                    return user
        except User.DoesNotExist:
            return None

    def _authenticate_by_email(self, request=None, **credentials):
        # Even though allauth will pass along `email`, other apps may
        # not respect this setting. For example, when using
        # django-tastypie basic authentication, the login is always
        # passed as `username`.  So let's place nice with other apps
        # and use username as fallback
        email = credentials.get('email', credentials.get('username'))
        if email:
            for user in filter_users_by_email(email):

                if user.is_superuser:
                    if user.check_password(credentials['password']):
                        return user

                is_member = self.organization_member(request, user)
                if is_member:
                    if user.check_password(credentials['password']):
                        return user
        return None

    def organization_member(self, request, user):
        organization = get_current_organization(request=request)
        return organization.is_member(user) if organization is not None else False
