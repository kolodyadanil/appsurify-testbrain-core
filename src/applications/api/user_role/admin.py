from django.contrib import admin
from .models import UserRole


class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'index')


# Register your models here.
admin.site.register(UserRole, UserRoleAdmin)
