# -*- coding: utf-8 -*-
import pathlib
import time
import os
import subprocess
from django.db import connection
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from applications.ml.models import MLModel, MLModelTests
from applications.ml.neural_network import MLTrainer
from applications.testing.models import TestSuite, Test


class QueryException(Exception):
    ...


def execute_query(query):
    psql_env = dict(
        PGHOST=settings.DATABASES["default"]["HOST"],
        PGPORT=str(settings.DATABASES["default"]["PORT"]),
        PGDATABASE=settings.DATABASES["default"]["NAME"],
        PGUSER=settings.DATABASES["default"]["USER"],
        PGPASSWORD=settings.DATABASES["default"]["PASSWORD"],
    )
    os_env = os.environ.copy()
    os_env.update(psql_env)

    psql_cmd = ["psql", "-c"] + [query]

    psql_process = subprocess.Popen(psql_cmd, env=os_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = psql_process.communicate()
    stdout = stdout.rstrip().lstrip()
    stderr = stderr.rstrip().lstrip()
    if stderr:
        psql_process.kill()
        raise QueryException(stderr)
    return stdout


def get_test_list(ml_model):
    with connection.cursor() as cursor:
        cursor.execute(ml_model.test_sql)
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return list([row['test_id'] for row in rows])


def fix_missed():
    test_suites = TestSuite.objects.filter(model=None)

    ml_models = MLModel.objects.bulk_create([
        MLModel(test_suite=test_suite)
        for test_suite in test_suites
    ])

    for ml_model in MLModel.objects.all():
        tests = Test.objects.filter(test_suites=ml_model.test_suite, models=None)
        MLModelTests.objects.bulk_create([
            MLModelTests(mlmodel=ml_model, test=test) for test in tests
        ], ignore_conflicts=True)

    return len(ml_models)


def fix_expired(days=7):
    queryset = MLModel.objects\
        .filter(dataset_status=MLModel.Status.SUCCESS)\
        .filter(updated__lte=datetime.now(timezone.utc) - timedelta(days=days))
    queryset.update(dataset_status=MLModel.Status.PENDING, model_status=MLModel.Status.PENDING)


def fix_broken(days=7):
    queryset = MLModel.objects\
        .filter(dataset_status=MLModel.Status.FAILURE)\
        .filter(updated__gte=datetime.now(timezone.utc) - timedelta(days=days))
    queryset.update(dataset_status=MLModel.Status.PENDING)

    queryset = MLModel.objects\
        .filter(model_status=MLModel.Status.FAILURE)\
        .filter(updated__gte=datetime.now(timezone.utc) - timedelta(days=days))
    queryset.update(model_status=MLModel.Status.PENDING)


def perform_dataset_to_csv(ml_model):
    _errors = list()

    ml_model.dataset_status = MLModel.Status.PROCESSING
    ml_model.save()

    dataset_path = ml_model.dataset_path
    dataset_path.mkdir(parents=True, exist_ok=True)

    test_id_list = get_test_list(ml_model=ml_model)
    ml_model_tests = MLModelTests.objects.filter(mlmodel=ml_model, test_id__in=test_id_list)

    for ml_model_test in ml_model_tests:
        test_id = ml_model_test.test_id

        try:
            sql = ml_model.dataset_sql(test_id=test_id)
            dataset_filename = f"{test_id}.csv"
            sql_query = f"\copy ({sql}) To '{dataset_path / dataset_filename}' With CSV DELIMITER ',' HEADER"
            ret = execute_query(query=sql_query)
            ml_model_test.status = MLModelTests.Status.SUCCESS
            ml_model_test.save()
        except QueryException as e:
            _errors.append(f"<TestID: {test_id}> {str(e)}")
            ml_model_test.status = MLModelTests.Status.FAILURE
            ml_model_test.save()
            continue
        except Exception as e:
            ml_model.dataset_status = MLModel.Status.FAILURE
            ml_model.save()
            ml_model_test.status = MLModelTests.Status.FAILURE
            ml_model_test.save()
            raise e

    if ml_model_tests.count() == len(_errors):
        ml_model.dataset_status = MLModel.Status.FAILURE
        ml_model.save()
        _message = '\n'.join(_errors)
        print(f"<TestSuite: {ml_model.test_suite_id}>:\n{_message}")
        return False

    ml_model.dataset_status = MLModel.Status.SUCCESS
    ml_model.model_status = MLModel.Status.PENDING
    ml_model.save()
    return True


def perform_model_train(ml_model):

    ml_model.model_status = MLModel.Status.PROCESSING
    ml_model.save()

    model_path, model_filename = ml_model.model_path
    model_path.mkdir(parents=True, exist_ok=True)
    try:
        mlt = MLTrainer(test_suite_id=ml_model.test_suite.id)
        mlt.train()

        ml_model.model_status = MLModel.Status.SUCCESS
        ml_model.save()
    except Exception as e:
        ml_model.model_status = MLModel.Status.FAILURE
        ml_model.save()
        raise e
