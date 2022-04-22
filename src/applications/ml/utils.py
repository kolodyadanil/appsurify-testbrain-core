# -*- coding: utf-8 -*-
from applications.ml.models import MLModel, States
from applications.testing.models import TestSuite


def initialize_empty_models():
    test_suites = TestSuite.objects.filter(models__isnull=True).distinct().order_by("project_id")
    for test_suite in test_suites:
        print(f"Initializing <TestSuite: {test_suite.id}>")
        MLModel.create_sequence(test_suite_id=test_suite.id)
    return True


def perform_prepare_models():
    print("Get TestSuites for storing datasets...")
    queryset = MLModel.objects.filter(state=States.PENDING).order_by("test_suite", "index", "updated")[:5]

    for ml_model in queryset:
        ml_model.save()
        try:
            print(f"Prepare <TestSuite: {ml_model.test_suite.id}>")
            result = ml_model.prepare()
            print(f"<TestSuite: {ml_model.test_suite.id}> - {result}")
        except Exception as e:
            print(f"<TestSuite: {ml_model.test_suite.id}> - {e}")
            continue


def perform_train_models():
    print("Get TestSuites for training datasets...")
    queryset = list(set(TestSuite.objects.filter(
        models__state=States.PREPARED).order_by("project", "id", "models__updated")))[:5]

    for test_suite in queryset:
        try:
            print(f"Train <TestSuite: {test_suite.id}>")
            result = MLModel.train_model(test_suite_id=test_suite.id)
            # print(f"<TestSuite: {test_suite.id}> - {result}")
        except Exception as e:
            # print(f"<TestSuite: {test_suite.id}> - {e}")
            continue
