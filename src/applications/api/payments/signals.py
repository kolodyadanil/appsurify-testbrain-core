from datetime import timedelta, datetime
import time

from django.db.models.signals import post_save
from django.db.models import Sum
from django.dispatch import receiver
from django.utils import timezone

from applications.testing.models import TestRunResult, TestRun

@receiver(post_save, sender=TestRunResult)
def update_time_saving_left_everytime_testrunresult_created(sender, instance, created, **kwargs):
    test_run_result = instance
    project = test_run_result.project
    organization = project.organization
    if organization.plan != organization.PLAN_FREE:
        return
    
    org_paid_until = organization.subscription_paid_until
    
    exec_times_last_60days = list()
    test_runs_last_60days = TestRun.objects.all().filter(
        updated__gte=datetime.now() - timedelta(days=60),
        project=project
        )
    if not test_runs_last_60days:
        return
    for test_run in test_runs_last_60days:
        test_run_results = test_run.test_run_results.all()
        test_run_exec_time = test_run_results.aggregate(
                Sum('execution_time'))['execution_time__sum']
        exec_times_last_60days.append(test_run_exec_time)
    longest_exec_time_last_60days = max(exec_times_last_60days) # x
    
    exec_times_this_paid_month = list()
    test_runs_this_paid_month = TestRun.objects.all().filter(
        updated__gte=datetime.fromtimestamp(org_paid_until) - timedelta(days=30),
        project=project)
    if not test_runs_this_paid_month:
        return
    for test_run in test_runs_this_paid_month:
        test_run_results = test_run.test_run_results.all()
        test_run_exec_time = test_run_results.aggregate(
                Sum('execution_time'))['execution_time__sum']
        exec_times_this_paid_month.append(test_run_exec_time)
    num_test_runs_this_paid_month = test_runs_this_paid_month.count() # y
    total_exec_times_this_paid_month = sum(exec_times_this_paid_month) # z
    
    time_saving = longest_exec_time_last_60days * num_test_runs_this_paid_month - total_exec_times_this_paid_month # x * y - z
    
    project.time_saving = time_saving
    project.save(update_fields=['time_saving'])
    
    total_time_saving = organization.projects.aggregate(
                Sum('time_saving'))['time_saving__sum']
    organization.time_saving_left = round(1000 * 60 - total_time_saving)
    if organization.time_saving_left < 0:
        organization.is_active = False
        organization.time_saving_left = 0
    organization.save(update_fields=['time_saving_left', 'is_active'])
