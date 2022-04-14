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
        price = request.data['priceId']['productPrice']
        customerEmail = request.data.get('userEmail')
        domain_url = os.getenv('DOMAIN')

        try:
            checkout_session = stripe.checkout.Session.create(
                success_url=domain_url + '/success',
                cancel_url=domain_url + '/canceled',
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

        return Response(status=status.HTTP_200_OK, data={"success": True})
