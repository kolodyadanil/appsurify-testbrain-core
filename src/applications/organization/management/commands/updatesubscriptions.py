"""
Management utility to update stripe subscriptions.
"""
import sys
from datetime import datetime, timedelta
import pytz

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from applications.organization.utils import default_org_model
from applications.organization.models import OrganizationUser, OrganizationOwner
from djstripe.models import Subscription, Customer
from applications.vcs.models import Commit


def error_handler(f):
    def wrapper(self, *args, **kwargs):
        try:
            return f(self, *args, **kwargs)
        except KeyboardInterrupt:
            self.stderr.write("\nOperation cancelled.")
            sys.exit(1)

        except NotRunningInTTYException:
            self.stdout.write(
                "Update stripe subscriptions skipped due to not running in a TTY. "
                "You can run `manage.py updatesubscriptions` in your project "
                "to create one manually."
            )

    return wrapper


class NotRunningInTTYException(Exception):
    pass


class Command(BaseCommand):
    help = 'Used to synchronize stripe subscriptions.'
    requires_migrations_checks = True

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.UserModel = get_user_model()
        self.OrgModel = default_org_model()
        self.OrgUserModel = OrganizationUser
        self.OrgOwnerModel = OrganizationOwner
        self.CustomerModel = Customer
        self.SubscriptionModel = Subscription
        self.CommitModel = Commit

    def execute(self, *args, **options):
        self.stdin = options.get('stdin', sys.stdin)  # Used for testing
        return super(Command, self).execute(*args, **options)

    @error_handler
    def handle(self, *args, **options):
        """count the number of active git users + number of admin users = number of subscriptions for the organization in stripe
        :param args:
        :param options:
        :return:
        """
        organizations = self.OrgModel.objects.filter(is_active=True)

        for organization in organizations:
            subscriptions_count = 0

            try:
                organization_owner = self.OrgOwnerModel.objects.get(organization_id=organization.id)
            except self.OrgOwnerModel.DoesNotExist:
                continue

            organization_owner_user = self.OrgUserModel.objects.get(
                organization_id=organization.id,
                id=organization_owner.organization_user_id)

            try:
                customer = self.CustomerModel.objects.get(subscriber_id=organization_owner_user.user_id)
            except self.CustomerModel.DoesNotExist:
                continue

            try:
                subscription = self.SubscriptionModel.objects.get(customer_id=customer.id)
            except self.SubscriptionModel.DoesNotExist:
                continue

            now = datetime.now().replace(tzinfo=pytz.UTC)
            delta = now - timedelta(days=90)  # for commits filter
            subscription_end_period = subscription.current_period_end.replace(tzinfo=pytz.UTC)
            date_difference = subscription_end_period - now

            # Update the day before the end of the subscription
            if date_difference.days <= 1:
                organization_users = self.OrgUserModel.objects.filter(organization_id=organization.id)

                for organization_user in organization_users:
                    if organization_user.is_admin is True:
                        subscriptions_count += 1
                    else:
                        commits_count = Commit.objects.filter(sender_id=organization_user.user_id, created__gte=delta,
                                                              created__lte=now).count()

                        if commits_count > 0:
                            subscriptions_count += 1

                if subscription.quantity != subscriptions_count:
                    subscription.update(quantity=subscriptions_count)
                    self.stdout.write(
                        self.style.SUCCESS('updated {org_name} have {subs_count}'.format(org_name=organization.name, subs_count=subscriptions_count)))
