from django.urls import path
from .views import StripeCheckoutView, StripeWebhookReceivedView

urlpatterns = [
    path('create-checkout-session/', StripeCheckoutView.as_view()),
    path('webhook/', StripeWebhookReceivedView.as_view()),
]
