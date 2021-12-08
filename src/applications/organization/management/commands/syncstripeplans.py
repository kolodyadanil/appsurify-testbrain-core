"""
Management utility to synchronize stripe plans.
"""
import sys

from django.core.management.base import BaseCommand
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
                "Synchronize stripe plans skipped due to not running in a TTY. "
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

    def execute(self, *args, **options):
        self.stdin = options.get('stdin', sys.stdin)  # Used for testing
        return super(Command, self).execute(*args, **options)

    @error_handler
    def handle(self, *args, **options):
        for plan in Plan.api_list():
            self.stdout.write(self.style.SUCCESS(plan.get('id')))
            Plan.sync_from_stripe_data(plan)
