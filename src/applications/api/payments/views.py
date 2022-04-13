import codecs
from rest_framework.utils import json

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.parsers import JSONParser, BaseParser, FormParser
from rest_framework.settings import api_settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ParseError
from rest_framework import status, renderers
from django.shortcuts import redirect
from system.env import env
import stripe

stripe.api_key = env.str('STRIPE_SECRET_KEY')

YOUR_DOMAIN = 'http://localhost:8000'


class StripeCheckoutView(APIView):
    def post(self, request):
        try:
            prices = stripe.Price.list(
                lookup_keys=[request.form['lookup_key']],
                expand=['data.product']
            )

            checkout_session = stripe.checkout.Session.create(
                line_items=[
                    {
                        'price': prices.data[0].id,
                        'quantity': 1,
                    },
                ],
                mode='subscription',
                success_url=YOUR_DOMAIN +
                            '?success=true&session_id={CHECKOUT_SESSION_ID}',
                cancel_url=YOUR_DOMAIN + '?canceled=true',
            )
            return redirect(checkout_session.url)
        except Exception as e:
            print(e)
            return Response(
                {'error': 'Something went wrong when creating stripe checkout session'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# @app.route('/create-portal-session', methods=['POST'])
# def customer_portal():
#     # For demonstration purposes, we're using the Checkout session to retrieve the customer ID.
#     # Typically this is stored alongside the authenticated user in your database.
#     checkout_session_id = request.form.get('session_id')
#     checkout_session = stripe.checkout.Session.retrieve(checkout_session_id)
#
#     # This is the URL to which the customer will be redirected after they are
#     # done managing their billing with the portal.
#     return_url = YOUR_DOMAIN
#
#     portalSession = stripe.billing_portal.Session.create(
#         customer=checkout_session.customer,
#         return_url=return_url,
#     )
#     return redirect(portalSession.url, code=303)
#

class CustomParser(BaseParser):
    """
    Parses JSON-serialized data.
    """
    # media_type = 'application/json'

    def parse(self, stream, media_type=None, parser_context=None):
        return stream


@authentication_classes([])
@permission_classes([])
class StripeWebhookReceivedView(APIView):
    # parser_classes = (CustomParser,)

    def post(self, request):
        endpoint_secret = env.str('STRIPE_WEBHOOK_SECRET')
        event = None
        payload = request.data

        sig_header = request.headers['STRIPE_SIGNATURE']

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError as e:
            # Invalid payload
            raise e
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            raise e

        # Handle the event
        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
        # ... handle other event types
        else:
            print('Unhandled event type {}'.format(event['type']))

        # return jsonify(success=True)
        return Response(status=status.HTTP_200_OK)

        # ''
        # # Replace this endpoint secret with your endpoint's unique secret
        # # If you are testing with the CLI, find the secret by running 'stripe listen'
        # # If you are using an endpoint defined with the API or dashboard, look in your webhook settings
        # # at https://dashboard.stripe.com/webhooks
        # webhook_secret = env.str('STRIPE_WEBHOOK_SECRET')
        # request_data = request.data
        #
        # if webhook_secret:
        #     # Retrieve the event by verifying the signature using the raw body and secret if webhook signing is configured.
        #     signature = request.headers.get('stripe-signature')
        #     try:
        #         event = stripe.Webhook.construct_event(
        #             payload=request.data, sig_header=signature, secret=webhook_secret)
        #         data = event['data']
        #     except Exception as e:
        #         return e
        #     # Get the type of webhook event sent - used to check the status of PaymentIntents.
        #     event_type = event['type']
        # else:
        #     data = request_data['data']
        #     event_type = request_data['type']
        # data_object = data['object']
        #
        # print('event ' + event_type)
        #
        # if event_type == 'checkout.session.completed':
        #     print('🔔 Payment succeeded!')
        # elif event_type == 'customer.subscription.trial_will_end':
        #     print('Subscription trial will end')
        # elif event_type == 'customer.subscription.created':
        #     print('Subscription created %s', event.id)
        # elif event_type == 'customer.subscription.updated':
        #     print('Subscription created %s', event.id)
        # elif event_type == 'customer.subscription.deleted':
        #     # handle subscription canceled automatically based
        #     # upon your subscription settings. Or if the user cancels it.
        #     print('Subscription canceled: %s', event.id)
        #
        # # return jsonify({'status': 'success'})
        # return Response(status=status.HTTP_200_OK)
