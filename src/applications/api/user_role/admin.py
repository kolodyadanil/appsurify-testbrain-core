from django.contrib import admin
from .models import UserRole


class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')


# Register your models here.
admin.site.register(UserRole, UserRoleAdmin)
