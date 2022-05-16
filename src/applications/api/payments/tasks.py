import time
import datetime
from dateutil.relativedelta import relativedelta

from celery import shared_task

from applications.organization.models import Organization

@shared_task
def update_organization_plan_task():
    updated = list()
    
    organizations = Organization.objects.all()
    for org in organizations:
        if org.subscription_paid_until < int(time.time()):
            org_info = {"org": org,
                        "from_plan": org.plan,
                        "to_plan": 'free'}
            org.plan = org.PLAN_FREE
            org.subscription_paid_until = int(
                time.mktime((datetime.datetime.today() + relativedelta(days=30)).timetuple()))
            org.time_saving_left = 1000
            updated.append(org_info)
    return f'Updated plan for {updated}'
