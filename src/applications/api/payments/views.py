import datetime
import os
import time

import stripe
from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.parsers import FileUploadParser
from rest_framework.response import Response
from rest_framework.views import APIView

from applications.organization.models import Organization
from system.env import env

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
        price = request.data['productPrice']
        customerEmail = request.data['customerEmail']
        # TODO: for testing, delete when we set 'DOMAIN' in .env
        domain_url = os.getenv('DOMAIN') or "https://appsurify.dev.appsurify.com"

        try:
            checkout_session = stripe.checkout.Session.create(
                success_url=domain_url + '/success',
                cancel_url=domain_url + '/canceled',
                mode='subscription',
                customer_email=customerEmail,
                line_items=[{
                    'price': price,
                    'quantity': 1
                }],
            )
            return Response(status=status.HTTP_200_OK, data={'id': checkout_session.id, 'url': checkout_session.url})
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

        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            user_email = payment_intent["charges"]["data"][0]["billing_details"]["email"]
            organizations = Organization.objects.all()
            if os.getenv('STRIPE_PRICE_ID'):
                for organization in organizations:
                    if organization.users.filter(email=user_email):
                        organization.subscription_paid_until = int(
                            time.mktime((datetime.datetime.today() + relativedelta(months=1)).timetuple()))
                        organization.save()
        elif event['type'] == 'customer.subscription.created':
            subscription = event['data']['object']
        else:
            print('Unhandled event type {}'.format(event['type']))
        return Response(status=status.HTTP_200_OK, data={"success": True})
