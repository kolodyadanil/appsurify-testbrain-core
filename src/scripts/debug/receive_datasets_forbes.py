# -*- coding: utf-8 -*-
import os
import sys
import time
import django
from django.utils import timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "system.settings")
django.setup()


from django.conf import settings


from applications.testing.models import TestSuite
from applications.ml.models import MLModel
from applications.ml.utils import *


def processing_dataset(test_suite, test):
    result = False
    dataset_filename = f"{test.id}.csv"

    project = test_suite.project
    organization = project.organization
    dataset_path = pathlib.PosixPath(settings.STORAGE_ROOT) / "ml_debug" / "datasets" / \
                   str(organization.id) / str(project.id) / str(test_suite.id)

    dataset_path.mkdir(parents=True, exist_ok=True)
    sql_template = open(settings.BASE_DIR / "scripts" / "debug" / "sql" / "dataset.sql", "r",
                        encoding="utf-8").read()
    sql = sql_template.format(test_suite_id=test_suite.id, test_id=test.id)
    sql_query = f"\copy ({sql}) To '{dataset_path / dataset_filename}' With CSV DELIMITER ',' HEADER"
    try:
        output = execute_query(query=sql_query)
        print(f"<TestSuiteID: {test_suite.id}> / <TestID: {test.id}> success {output}")
        result = True
    except Exception as e:
        print(f"<TestSuiteID: {test_suite.id}> / <TestID: {test.id}> {str(e)}")
    return result


def main():
    print("Get TestSuites for storing datasets...")
    test_suite_queryset = TestSuite.objects.filter(project__organization__name='forbes').distinct()

    for test_suite in test_suite_queryset:
        test_queryset = Test.objects.filter(test_suites=test_suite).distinct()

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = {}

            for test in test_queryset:
                futures.update({executor.submit(processing_dataset, test_suite, test): test})

            for future in concurrent.futures.as_completed(futures):
                test = futures[future]
                result = future.result()
                print(f"Test: '{test.name}' - {result}")


if __name__ == "__main__":
    main()
