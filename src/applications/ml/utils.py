# -*- coding: utf-8 -*-
import logging
from applications.ml.models import MLModel, States
from applications.testing.models import TestSuite

# log = logging.getLogger(__name__)
log = logging.getLogger('applications.ml')


def initialize_empty_models():

    _total = 0
    _success = 0
    _fail = 0
    _current = 0

    test_suites = TestSuite.objects.filter(models__isnull=True).distinct().order_by("project_id")

    for test_suite in test_suites:
        try:
            result = MLModel.create_sequence(test_suite_id=test_suite.id)
        except Exception as exc:
            continue


def perform_prepare_models():

    _total = 0
    _success = 0
    _fail = 0
    _current = 0

    queryset = MLModel.objects.filter(state=States.PENDING).order_by("test_suite", "index", "updated")[:10]

    for ml_model in queryset:
        ml_model.save()

        try:
            result = ml_model.prepare()
        except Exception as exc:
            continue


def perform_train_models():

    _total = 0
    _success = 0
    _fail = 0
    _current = 0

    queryset = list(set(TestSuite.objects.filter(
        models__state=States.PREPARED).order_by("project", "id", "models__updated")))[:10]

    for test_suite in queryset:
        try:
            result = MLModel.train_model(test_suite_id=test_suite.id)
        except Exception as exc:
            continue
