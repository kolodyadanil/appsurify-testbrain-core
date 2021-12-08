from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class AccountConfig(AppConfig):
    name = 'applications.allauth.account'
    label = 'account'
    verbose_name = _('Accounts')
