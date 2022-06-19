from django.urls import path

from .views import UserRolesView

urlpatterns = [
    path('user_roles/', UserRolesView.as_view()),
]
