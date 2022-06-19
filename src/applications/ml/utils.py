import datetime
from dateutil.relativedelta import relativedelta
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


def months_between(start_date, end_date):
    """
    Given two instances of ``datetime.date``, generate a list of dates on
    the 1st of every month between the two dates (inclusive).

    e.g. "5 Jan 2020" to "17 May 2020" would generate:

        1 Jan 2020, 1 Feb 2020, 1 Mar 2020, 1 Apr 2020, 1 May 2020

    """
    if start_date > end_date:
        raise ValueError(f"Start date {start_date} is not before end date {end_date}")

    year = start_date.year
    month = start_date.month

    while (year, month) <= (end_date.year, end_date.month):
        yield datetime.date(year, month, 1)

        if month == 12:
            month = 1
            year += 1
        else:
            month += 1