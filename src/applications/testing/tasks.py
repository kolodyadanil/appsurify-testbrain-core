# -*- coding: utf-8 -*-
from system.celery_app import app

import functools
import time

from celery.exceptions import Reject
from hashlib import md5
from contextlib import contextmanager

from django.core.cache import cache
# from celery_locked_task.locked_task import LockedTask


@app.task(bind=True)
def add_caused_by_commits_task(self, defect_id, commit_id, test_suite_id):
    from applications.testing.models import Defect, TestSuite
    from applications.vcs.models import Commit

    defect = Defect.objects.filter(pk=defect_id)
    commit = Commit.objects.filter(pk=commit_id)
    test_suite = TestSuite.objects.filter(pk=test_suite_id)

    if defect.exists() and commit.exists() and test_suite.exists():
        defect = defect.first()
        commit = commit.first()
        test_suite = test_suite.first()
    else:
        return False

    defect.add_caused_by_commits(commit, test_suite)


@app.task(bind=True)
def add_closed_by_commits_task(self, defect_id, commit_id, test_suite_id):
    from applications.testing.models import Defect, TestSuite
    from applications.vcs.models import Commit

    defect = Defect.objects.filter(pk=defect_id)
    commit = Commit.objects.filter(pk=commit_id)
    test_suite = TestSuite.objects.filter(pk=test_suite_id)

    if defect.exists() and commit.exists() and test_suite.exists():
        defect = defect.first()
        commit = commit.first()
        test_suite = test_suite.first()
    else:
        return False

    defect.add_closed_by_commits(commit, test_suite)


@app.task(bind=True)
def build_test_prioritization_ml_model_for_test_suite(self, test_suite_id):
    import pytz
    import datetime
    from applications.testing.models import TestSuite
    from applications.testing.utils.predict_tests_priorities.predict_tests_priorities import MLTrainer, DatasetError

    try:
        mlt = MLTrainer(test_suite_id=test_suite_id)
        mlt.train()
        current_time = datetime.datetime.now().replace(tzinfo=pytz.timezone('UTC'))
        TestSuite.objects.filter(id=test_suite_id).update(ml_model_last_time_created=current_time)
    except DatasetError as e:
        return e.message


@app.task(bind=True)
def build_test_prioritization_ml_models(self):
    import pytz
    import datetime
    from django.db.models import Q
    from applications.testing.models import TestSuite

    current_time = datetime.datetime.now().replace(tzinfo=pytz.timezone('UTC'))
    one_day_before_from_now = current_time - datetime.timedelta(days=1)
    minimal_number_associated_test_runs = 50
    minimal_number_test_run_results = 100

    test_suites = TestSuite.objects.filter(
        test_runs__gte=minimal_number_associated_test_runs,
        test_run_results__gte=minimal_number_test_run_results
    ).filter(
        Q(ml_model_last_time_created__isnull=True) |
        Q(ml_model_last_time_created__lte=one_day_before_from_now)
    ).distinct('id')[:1000]
    # For each test_suite in result start celery task for building model
    test_suites_list = list(set(test_suites.values_list('id', flat=True)))
    for test_suite_id in test_suites_list:
        try:
            build_test_prioritization_ml_model_for_test_suite.delay(test_suite_id)
        except Exception as exc:
            print(exc.message)
