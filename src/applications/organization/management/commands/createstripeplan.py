"""
Management utility to create stripe plan.
"""
import sys

from django.core.management.base import BaseCommand
from django.core import exceptions
from djstripe.models import Plan


def error_handler(f):
    def wrapper(self, *args, **kwargs):
        try:
            return f(self, *args, **kwargs)
        except KeyboardInterrupt:
            self.stderr.write("\nOperation cancelled.")
            sys.exit(1)

        except NotRunningInTTYException:
            self.stdout.write(
                "Create stripe plan skipped due to not running in a TTY. "
                "You can run `manage.py syncstripeplans` in your project "
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
        self.PlanModel = Plan
        self.stripe_id_field = self.PlanModel._meta.get_field('stripe_id')
        self.amount_field = self.PlanModel._meta.get_field('amount')
        self.interval_field = self.PlanModel._meta.get_field('interval')
        self.currency_field = self.PlanModel._meta.get_field('currency')
        self.name_field = self.PlanModel._meta.get_field('name')
        self.trial_period_days_field = self.PlanModel._meta.get_field('trial_period_days')

    def execute(self, *args, **options):
        self.stdin = options.get('stdin', sys.stdin)  # Used for testing
        return super(Command, self).execute(*args, **options)

    @error_handler
    def handle(self, *args, **options):
        stripe_id = self.get_input_data(self.stripe_id_field, u'Stripe id: ')
        amount = self.get_input_data(self.amount_field, u'Amount to be charged on the interval specified: ')
        interval = self.get_input_data(self.interval_field,
                                       u'The number of intervals (specified in the interval property) between each subscription billing (month, year, week, day): ')

        if interval not in ['month', 'year', 'week', 'day']:
            raise Exception('Invalid interval: must be one of month, year, week, or day')

        currency = self.get_input_data(self.currency_field, u'Three-letter ISO currency code: ')
        name = self.get_input_data(self.name_field,
                                   u'Name of the plan, to be displayed on invoices and in the web interface: ')
        trial_period_days = self.get_input_data(self.trial_period_days_field,
                                                u'Number of trial period days granted when subscribing a customer to this plan. Null if the plan has no trial period: ')

        plan = self.PlanModel.create(stripe_id=stripe_id, amount=amount, interval=interval, currency=currency,
                                     name=name, trial_period_days=trial_period_days)
        self.stdout.write(self.style.SUCCESS('%s created' % plan))

    def get_input_data(self, field, message, default=None):
        """
        Override this method if you want to customize data inputs or
        validation exceptions.
        """
        raw_value = input(message)
        if default and raw_value == '':
            raw_value = default
        try:
            val = field.clean(raw_value, None)
        except exceptions.ValidationError as e:
            self.stderr.write("Error: %s" % '; '.join(e.messages))
            val = None

        return val
