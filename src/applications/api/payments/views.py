import codecs
import os
from django.views.generic.base import TemplateView
from rest_framework.utils import json

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.parsers import JSONParser, BaseParser, FormParser, FileUploadParser
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


class StripePublicKeys(APIView):
    def get(self, request, *args, **kwargs):
        keys = {
            'publishableKey': os.getenv('STRIPE_PUBLISHABLE_KEY'),
            'productPrice': os.getenv('STRIPE_PRICE_ID')
        }
        return Response(status=status.HTTP_200_OK, data=keys)


class StripeCheckoutView(APIView):
    def post(self, request):
        price = request.POST.get('productPrice')
        customerEmail = request.POST.get('customerEmail')
        domain_url = os.getenv('DOMAIN')

        try:
            # Create new Checkout Session for the order
            # Other optional params include:
            # [billing_address_collection] - to display billing address details on the page
            # [customer] - if you have an existing Stripe Customer ID
            # [customer_email] - lets you prefill the email input in the form
            # [automatic_tax] - to automatically calculate sales tax, VAT and GST in the checkout page
            # For full details see https://stripe.com/docs/api/checkout/sessions/create

            # ?session_id={CHECKOUT_SESSION_ID} means the redirect will have the session ID set as a query param
            checkout_session = stripe.checkout.Session.create(
                success_url=domain_url + '/success.html?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=domain_url + '/canceled.html',
                mode='subscription',
                # automatic_tax={'enabled': True},
                customer_email=customerEmail,
                line_items=[{
                    'price': price,
                    'quantity': 1
                }],
            )
            return redirect(checkout_session.url, code=303)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': {'message': str(e)}})


class StripeCheckoutSession(APIView):
    # Fetch the Checkout Session to display the JSON result on the success pag    @app.route('/checkout-session', methods=['GET'])
    def get(self, request, *args, **kwargs):
        id = request.args.get('sessionId')
        checkout_session = stripe.checkout.Session.retrieve(id)
        return Response(status=status.HTTP_200_OK, data=checkout_session)


@authentication_classes([])
@permission_classes([])
class StripeWebhookReceivedView(APIView):
    parser_classes = (FileUploadParser,)

    def post(self, request):
        endpoint_secret = env.str('STRIPE_WEBHOOK_SECRET')
        event = None
        payload = request.stream.body

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
        print(event['data']['object'])
        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
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
