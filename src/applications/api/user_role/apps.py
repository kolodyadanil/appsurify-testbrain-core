from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class UserRoleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'applications.api.user_role'
    verbose_name = _('User Roles')
