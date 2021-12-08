# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.http import HttpResponse

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


from applications.organization.utils import get_current_organization
# from applications.license.models import LicenseKey
# from .serializers import LicenseKeySerializer
from django.contrib.auth.models import User


# from applications.license.utils import get_usage
from applications.vcs.models import Commit
from applications.testing.models import TestSuite
# from djstripe.models import Customer
# import stripe
from django.conf import settings
from dateutil import parser
from datetime import datetime
from applications.api.common.utils import get_stripe_secret_key
from rest_framework.views import APIView
# stripe.api_key = get_stripe_secret_key(settings.STRIPE_LIVE_MODE)


# class LicenseModelViewSet(ReadOnlyModelViewSet):
#
#     model = LicenseKey
#     queryset = LicenseKey.objects.all()
#     serializer_class = LicenseKeySerializer
#     permission_classes = (IsAuthenticated,)
#
#     def get_queryset(self):
#         queryset = super(LicenseModelViewSet, self).get_queryset()
#         user = self.request.user
#         if user.is_superuser:
#             return queryset
#
#         organization = get_current_organization(request=self.request)
#         if organization:
#             queryset = queryset.filter(organization=organization)
#
#         return queryset
#
#     @action(
#         methods=[
#             "GET",
#         ],
#         detail=True,
#         url_path=r"download",
#     )
#     def download(self, request, pk, *args, **kwargs):
#
#         lic = self.get_object()
#
#         response = HttpResponse(status=status.HTTP_200_OK, content_type="text/plain")
#         response["Content-Disposition"] = 'attachment; filename="{}"'.format(lic.uuid)
#         response.write(LicenseKey.encode(lic._dict()))
#         return response
#
#     @action(
#         methods=[
#             "GET",
#         ],
#         detail=False,
#         url_path=r"information-dashboard-table",
#     )
#     def get_information_dashboard_table(self, request):
#         try:
#             organization = get_current_organization(request=request)
#
#             # get commiters from all repositories for this organization
#             committers = Commit.objects.filter(
#                 project__organization=organization
#             )  # next annotate or aggregate (see docs)
#
#             uniqueCommitters = []
#             for item in committers:
#                 committer = item.committer
#                 if committer["email"] not in uniqueCommitters:
#                     if (parser.parse(committer["date"])).month == datetime.now().month:
#                         uniqueCommitters.append(committer["email"])
#
#             test_suites = TestSuite.objects.filter(project__organization=organization)
#             test_suites_usage_sum = 0
#             for test_suite in test_suites:
#                 test_suites_usage_sum += get_usage(test_suite_id=test_suite.id)
#             return Response(
#                 {
#                     "organization": {
#                         "name": organization.name,
#                         "domain": organization.site.domain,
#                         "deploy": organization.deploy_type
#                     },
#                     "committers": len(uniqueCommitters),
#                     "usage": test_suites_usage_sum,
#                 },
#                 status=status.HTTP_200_OK,
#             )
#         except Exception as e:
#             return Response(
#                 data={"detail": e.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
#
#     @action(methods=["POST"], detail=False, url_path=r"create-checkout-session")
#     def checkout_payments(self, request, **kwargs):
#         req = request.data
#         if req["committers"] < 1:
#             return Response(
#                 data={"detail": "The commiters equal 0"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )
#         try:
#             checkout_session = stripe.checkout.Session.create(
#                 success_url=req["success_url"],
#                 cancel_url=req["cancel_url"],
#                 payment_method_types=["card"],
#                 mode="subscription",
#                 customer=req["customer_id"],
#                 line_items=[
#                     {
#                         "price": settings.STRIPE_PRICE_ID,
#                         "quantity": req["committers"],
#                     }
#                 ],
#             )
#             return Response(
#                 data=checkout_session,
#                 status=status.HTTP_200_OK,
#             )
#         except Exception as e:
#             return Response(
#                 data={"detail": e.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
#
#     @action(methods=["PUT"], detail=False, url_path=r"update-subscription-payment")
#     def update_subscription_payment(self, request, **kwargs):
#         req = request.data
#         new_quantity = req["new_committers"]
#         try:
#             subscription = stripe.Subscription.retrieve(req["subscription_id"])
#             if subscription["items"]["data"][0].quantity != new_quantity:
#                 stripe.Subscription.modify(
#                     subscription.id,
#                     cancel_at_period_end=False,
#                     proration_behavior="none",
#                     items=[
#                         {
#                             "id": subscription["items"]["data"][0].id,
#                             "quantity": new_quantity,
#                         }
#                     ],
#                 )
#                 return Response(
#                     data={"id_subscription": subscription.id},
#                     status=status.HTTP_200_OK,
#                 )
#             return Response(
#                 data={"detail": "The quantity does not change"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )
#         except Exception as e:
#             return Response(
#                 data={"detail": e.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
#
#     @action(
#         methods=[
#             "GET",
#         ],
#         detail=False,
#         url_path=r"get_subscription",
#     )
#     def get_subscription_by_customer(self, request):
#         try:
#             subs = stripe.Subscription.list()
#             subscription_id = ""
#             customer_id = request.GET.get("customer_id")
#             quantity = 0
#             for item in subs["data"]:
#                 if item.customer == customer_id:
#                     subscription_id = item.id
#                     quantity = item.quantity
#                     return Response(
#                         data={
#                             "subscription_id": subscription_id,
#                             "customer_id": customer_id,
#                             "quantity": quantity,
#                         },
#                         status=status.HTTP_200_OK,
#                     )
#             return Response(
#                 data={"detail": "Not found subscription in the stripe payments"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )
#         except Exception as e:
#             return Response(
#                 data={"detail": e.message},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             )
#
#     @action(
#         methods=[
#             "GET",
#         ],
#         detail=False,
#         url_path=r"get_customer_stripe",
#     )
#     def get_customer_by_user(self, request):
#         try:
#             customer_id = Customer.objects.get(
#                 subscriber_id=request.GET.get("user_id")
#             ).stripe_id
#             if len(customer_id):
#                 return Response(
#                     data={
#                         "customer_id": customer_id,
#                     },
#                     status=status.HTTP_200_OK,
#                 )
#             return Response(
#                 data={"detail": "Not found customter in the stripe payments"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )
#         except Exception as e:
#             print(e)
#             return Response(
#                 data={"detail": e.message},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             )


class DashboardDummyAPIView(APIView):
    def get(self, request, *args, **kwargs):

        return Response({}, status=status.HTTP_200_OK)
