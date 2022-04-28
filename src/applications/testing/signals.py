# -*- coding: utf-8 -*-
from __future__ import unicode_literals


from django.db.models.signals import pre_init, post_init, pre_save, post_save, m2m_changed
from django.dispatch import receiver
from copy import deepcopy

from applications.project.models import Project
from applications.vcs.models import *

from .models import *


@receiver(post_save, sender=Project)
def model_project_auto_create_defaults(sender, instance, created, **kwargs):

    if created:
        area = Area.get_default(project=instance)
        test_type = TestType.get_default(project=instance)


@receiver(pre_save, sender=Test)
def model_test_autoset_associated_areas(sender, instance, **kwargs):
    if instance.pk:
        db_instance = Test.objects.get(id=instance.pk)
        if db_instance.area != instance.area and instance.area:
            instance.update_associated_areas_by_linked_areas()
    return


@receiver(post_save, sender=Test)
def model_test_autoset_default_area(sender, instance, created, **kwargs):
    test = instance
    if created:
        test.associated_areas.add(*list(test.area.links.all()))

    if test.area is None:
        area = Area.get_default(project=test.project)
        test.area = area
        instance.update_associated_areas_by_linked_areas()
        test.save()


@receiver(post_save, sender=TestSuite)
def model_test_suite_autoset_default_test_type(sender, instance, created, **kwargs):
    test_suite = instance
    if created:
        if test_suite.test_type is None:
            test_type = TestType.get_default(project=test_suite.project)
            test_suite.test_type = test_type
            test_suite.save()


@receiver(pre_save, sender=TestRun)
def model_test_run_set_name(sender, instance, **kwargs):
    test_run = instance
    name = test_run.generate_name()
    test_run.name = name


@receiver(m2m_changed, sender=TestRun.tests.through)
def model_test_run_tests_changed(sender, instance, reverse, model, pk_set, action, **kwargs):
    test_run = instance
    tests = model.objects.filter(pk__in=pk_set)
    if action == 'post_add':
        test_run.areas.set(tests.filter(area__isnull=False).values_list('area_id', flat=True))
        test_run.create_pending_test_run_results()

    if action == 'pre_delete':
        # print "Test deleted"
        # print "PK: ", pk_set
        pass


@receiver(post_save, sender=TestRunResult)
def model_test_run_result_complete_test_run(sender, instance, created, **kwargs):
    test_run_result = instance
    test_suite = test_run_result.test_suite
    test_run = test_run_result.test_run
    test = test_run_result.test
    commit = test_run_result.commit

    if test_run.test_run_results.all().count() == test_run.test_run_results.exclude(status=TestRunResult.STATUS_PENDING).count():
        test_run.status = TestRun.STATUS_COMPLETE
        test_run.end_date = timezone.now()
        test_run.save()
        test_run.test_run_results.update(test_run_status=test_run.status, test_run_end_date=test_run.end_date)


@receiver(post_init, sender=Defect)
def model_defect_post_init(sender, instance, *args, **kwargs):
    original = deepcopy(instance)
    setattr(instance, '__original', original)


@receiver(pre_save, sender=Defect)
def model_defect_state_detect(sender, instance, **kwargs):
    original = getattr(instance, '__original', None)


@receiver(post_save, sender=Defect)
def model_defect_send_mail(sender, instance, created, **kwargs):
    original = getattr(instance, '__original', None)
    defect = instance

    if defect.status != Defect.STATUS_CLOSED and original.pk is None:
        defect.send_notification_mail(open=True)

    elif defect.status != Defect.STATUS_CLOSED and original.status == Defect.STATUS_CLOSED:
        defect.send_notification_mail(reopen=True)

    elif defect.status == Defect.STATUS_CLOSED and original.status != Defect.STATUS_CLOSED:
        defect.send_notification_mail(close=True)


@receiver(pre_save, sender=TestRunResult)
def model_test_run_result_calculate_execution_time(sender, instance, **kwargs):
    test_run_result = instance
    execution_time = test_run_result.get_execution_time()
    test_run_result.execution_time = execution_time


@receiver(pre_save, sender=TestRunResult)
def model_test_run_result_perform_related_fields(sender, instance, **kwargs):
    test_run_result = instance

    test_run_result.project_name = test_run_result.project.name
    test_run_result.test_type_name = test_run_result.test_type.name

    test_run_result.test_suite_name = test_run_result.test_suite.name
    test_run_result.test_suite_target_type = test_run_result.test_suite.target_type
    test_run_result.test_suite_created = test_run_result.test_suite.created
    test_run_result.test_suite_updated = test_run_result.test_suite.updated

    test_run_result.test_run_name = test_run_result.test_run.name
    test_run_result.test_run_type = test_run_result.test_run.type
    test_run_result.test_run_status = test_run_result.test_run.status
    test_run_result.test_run_is_local = test_run_result.test_run.is_local
    test_run_result.test_run_start_date = test_run_result.test_run.start_date
    test_run_result.test_run_end_date = test_run_result.test_run.end_date
    test_run_result.test_run_created = test_run_result.test_run.created
    test_run_result.test_run_updated = test_run_result.test_run.updated

    if test_run_result.area is not None:
        test_run_result.area_name = test_run_result.area.name
        test_run_result.area_created = test_run_result.area.created
        test_run_result.area_updated = test_run_result.area.updated
    else:
        test_run_result.area_name = test_run_result.test.area.name
        test_run_result.area_created = test_run_result.test.area.created
        test_run_result.area_updated = test_run_result.test.area.updated

    test_run_result.test_name = test_run_result.test.name
    test_run_result.test_created = test_run_result.test.created
    test_run_result.test_updated = test_run_result.test.updated

    if test_run_result.step is not None:
        step = test_run_result.test.teststep_set.get(step=test_run_result.step)
        test_run_result.step_name = step.name
        test_run_result.step_index_number = step.index_number

    if test_run_result.commit is not None:
        test_run_result.commit_timestamp = test_run_result.commit.timestamp
        test_run_result.commit_display_id = test_run_result.commit.display_id
        test_run_result.commit_created = test_run_result.commit.created
        test_run_result.commit_updated = test_run_result.commit.updated


@receiver(post_save, sender=TestRunResult)
def model_test_run_result_perform_defect(sender, instance, created, **kwargs):
    test_run_result = instance
    test = test_run_result.test
    test_run = test_run_result.test_run
    test_suite = test_run_result.test_suite

    project = test_run_result.project
    commit = test_run_result.commit

    auto_raise = test_suite.auto_raise_defect
    auto_close = test_suite.auto_close_defect
    defect = Defect.perform(test_run_result=test_run_result)


from applications.ml.neural_network_flaky import MLPredictor as FlakyMLPredictor
@receiver(post_save, sender=Defect)
def set_defect_as_flaky(sender, instance, created, **kwargs):
    defect = instance
    associated_tests = defect.associated_tests.all()
    for test in associated_tests:
        try:
            test_run = test.recently_test_runs[0]
            if test_run.status == TestRun.STATUS_COMPLETE:
                if not FlakyMLPredictor.is_loaded:
                    test_run_results = test_run.test_run_results.all().values_list('status', flat=True)
                    if Defect.is_flaky(test_run_results):
                        defect.type = Defect.TYPE_FLAKY
                    return 0
                if FlakyMLPredictor._predict_defect_flakiness(defect) >= 0.8:
                    defect.type = Defect.TYPE_FLAKY
                    return 1
                else:
                    test_run_results = test_run.test_run_results.all().values_list('status', flat=True)
                    if Defect.is_flaky(test_run_results):
                        defect.type = Defect.TYPE_FLAKY
                return 2
        except:
            continue

@receiver(post_save, sender=TestRun)
def create_defect_and_add_commits_in_last_24hours(sender, instance, created, **kwargs):
    test_suite = instance.test_suite
    test_runs = TestRun.objects.filter(test_suite=test_suite).order_by('id')
    
    if instance == test_runs.first(): # If this is the first test of test suite, pass over this function
        print('First test run in current test suite, do nothing')
    
    else:
        timestamp_24hours_ago = timezone.now() - timezone.timedelta(hours=24)
        last_24hours_commits = Commit.objects.filter(timestamp__gte=timestamp_24hours_ago)
        
        defect = Defect(project=test_suite.project,
                        name='Create for ...',
                        reason='Create for ... ',
                        error='Not yet',
                        type=Defect.TYPE_NEW_TEST,
                        create_type=Defect.CREATE_TYPE_AUTOMATIC,
                        status=Defect.STATUS_NEW,
                        severity=Defect.SEVERITY_TRIVIAL,
                        # remain fields are set to Blank or Default
                        )
        defect.save()

        for commit in last_24hours_commits:
            defect.add_caused_by_commits(commit=commit, test_suite=test_suite)
            defect.add_closed_by_commits(commit=commit, test_suite=test_suite)
