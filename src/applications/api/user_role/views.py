from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import UserRoleSerializer

from .models import UserRole


# Create your views here.
class UserRolesView(APIView):
    def get(self, request):
        queryset = UserRole.objects.all()
        serializer = UserRoleSerializer(queryset, many=True)
        return Response(serializer.data)
