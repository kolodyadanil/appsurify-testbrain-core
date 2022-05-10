from django.urls import path
from django.views.generic import TemplateView

from .views import StripeCheckoutView, StripeWebhookReceivedView, StripePublicKeys, StripeCheckoutSession, \
    StripeGetSubscriptionActiveSeats

urlpatterns = [
    path('create-checkout-session/', StripeCheckoutView.as_view()),
    path('checkout-session/', StripeCheckoutSession.as_view()),
    path('public_keys/', StripePublicKeys.as_view()),
    path('webhook/', StripeWebhookReceivedView.as_view()),
    path('seats/', StripeGetSubscriptionActiveSeats.as_view()),
    # TODO: for cors test
    path('index/', TemplateView.as_view(template_name="index.html")),
]
