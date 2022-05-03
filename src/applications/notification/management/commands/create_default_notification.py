import datetime

import pytz
from django.core.management import BaseCommand

from applications.notification.models import Notification
from applications.project.models import Project


class Command(BaseCommand):

    def handle(self, *args, **options):
        projects = Project.objects.all()
        Notification.objects.filter(type=Notification.TYPE_RISK,
                                    period=Notification.PERIOD_WEEKLY, schedule_hour=0,
                                    schedule_weekday=7, schedule_timezone='US/Pacific').delete()
        for project in projects:
            Notification.objects.get_or_create(project=project, type=Notification.TYPE_RISK,
                                               period=Notification.PERIOD_WEEKLY, schedule_hour=0,
                                               schedule_weekday=7, schedule_timezone='US/Pacific',
                                               emails=project.owner.project_user.user.email,
                                               schedule_last_send=datetime.datetime.now().replace(
                                                   tzinfo=pytz.timezone('UTC')))
