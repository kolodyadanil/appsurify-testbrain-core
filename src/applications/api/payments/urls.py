from django.urls import path

from .views import StripeCheckoutView, StripeWebhookReceivedView, StripePublicKeys, StripeCheckoutSession

urlpatterns = [
    path('create-checkout-session/', StripeCheckoutView.as_view()),
    path('checkout-session/', StripeCheckoutSession.as_view()),
    path('public_keys/', StripePublicKeys.as_view()),
    path('webhook/', StripeWebhookReceivedView.as_view()),
]
