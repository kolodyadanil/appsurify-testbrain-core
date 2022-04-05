from rest_framework import serializers

from applications.api.user_role.models import UserRole


class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = ('id', 'name')

    name = serializers.CharField(max_length=255)
