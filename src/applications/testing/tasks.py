# -*- coding: utf-8 -*-
from system.celery_app import app

from celery import group

import functools
import time

from celery.exceptions import Reject
from hashlib import md5
from contextlib import contextmanager

from django.core.cache import cache


from applications.vcs.utils.association import find_and_associate_areas, find_and_association_files


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
def add_association_for_test(self, test_id):
    from applications.testing.models import Test
    tests = Test.objects.filter(id=test_id)
    for test in tests:
        result_areas = find_and_associate_areas(test)
        result_files = find_and_association_files(test)


@app.task(bind=True)
def periodic_add_association(self, chunk_size=20):
    from applications.project.models import Project
    from celery.utils.functional import chunks
    test_ids = list(Project.objects.order_by('-id').exclude(tests__isnull=True)
                    .values_list('tests__id', flat=True).distinct())
    for chunk in chunks(test_ids, chunk_size):
        # add_association_for_test.delay(chunk)
        job = group([add_association_for_test.s(test_id) for test_id in chunk])
        result = job.apply_async()
        time.sleep(0.5)


@app.task(bind=True)
def update_materialized_view(self, *args, **kwargs):
    from applications.testing.models import TestRunMaterializedModel
    TestRunMaterializedModel.refresh()
