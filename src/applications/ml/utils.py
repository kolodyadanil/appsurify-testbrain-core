# -*- coding: utf-8 -*-
import pathlib
import time
import concurrent.futures
import os
import subprocess
from django.db import connection
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from applications.ml.models import MLModel
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


def processing_dataset(ml_model):
    result = False
    ml_model.dataset_status = MLModel.Status.PROCESSING
    ml_model.save()
    dataset_filename = ml_model.dataset_filename
    dataset_path = ml_model.dataset_path
    dataset_path.mkdir(parents=True, exist_ok=True)
    test_id = ml_model.test_id
    print(f"<TestSuiteID: {ml_model.test_suite_id}> / <TestID: {ml_model.test_id}> processing...")
    sql = ml_model.dataset_sql
    sql_query = f"\copy ({sql}) To '{dataset_path / dataset_filename}' With CSV DELIMITER ',' HEADER"
    try:
        output = execute_query(query=sql_query)
        print(f"<TestSuiteID: {ml_model.test_suite_id}> / <TestID: {ml_model.test_id}> success {output}")
        ml_model.dataset_status = MLModel.Status.SUCCESS
        ml_model.model_status = MLModel.Status.PENDING
        ml_model.save()
        result = True
    except Exception as e:
        print(f"<TestSuiteID: {ml_model.test_suite_id}> / <TestID: {ml_model.test_id}> {str(e)}")
        ml_model.dataset_status = MLModel.Status.FAILURE
        ml_model.save()
    return result


def fix_missed():
    test_suites = TestSuite.objects.filter(tests__models__isnull=True).distinct().order_by("id")

    for test_suite in test_suites:
        print(f"Checking <TestSuite: {test_suite.id}>")
        test_ids = MLModel.get_test_list(test_suite=test_suite)
        MLModel.objects.bulk_create([
            MLModel(test_suite_id=test_suite.id, test_id=test_id)
            for test_id in test_ids
        ], ignore_conflicts=True)
    return True


def fix_expired(days=7):
    queryset = MLModel.objects\
        .filter(dataset_status=MLModel.Status.SUCCESS)\
        .filter(updated__lte=datetime.now(timezone.utc) - timedelta(days=days))
    queryset.update(dataset_status=MLModel.Status.PENDING, model_status=MLModel.Status.PENDING)


def fix_broken(days=7):
    queryset = MLModel.objects\
        .filter(dataset_status=MLModel.Status.FAILURE)\
        .filter(updated__lte=datetime.now(timezone.utc) - timedelta(days=days))
    queryset.update(dataset_status=MLModel.Status.PENDING)

    queryset = MLModel.objects\
        .filter(model_status=MLModel.Status.FAILURE)\
        .filter(updated__gte=datetime.now(timezone.utc) - timedelta(days=days))
    queryset.update(model_status=MLModel.Status.PENDING)


def perform_dataset_to_csv(test_suite):

    test_id_list = MLModel.get_test_list(test_suite=test_suite)
    print(f"--- Total tests: {len(test_id_list)} ---")
    ml_models = MLModel.objects.filter(test_suite_id=test_suite.id, test_id__in=test_id_list,
                                       dataset_status=MLModel.Status.PENDING)
    _complete = 0

    print(f"--- Total models: {ml_models.count()} ---")
    for ml_model in ml_models:
        result = processing_dataset(ml_model=ml_model)
        if result:
            _complete += 1
    print(f"--- Success models: {_complete} ---")
    return _complete


def perform_multi_dataset_to_csv(test_suite):
    test_id_list = MLModel.get_test_list(test_suite=test_suite)
    ml_models = MLModel.objects.filter(test_suite_id=test_suite.id, test_id__in=test_id_list,
                                       dataset_status=MLModel.Status.PENDING)
    _complete = 0

    print(f"--- Total models: {ml_models.count()} ---")

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {}
        for ml_model in ml_models:
            futures.update({executor.submit(processing_dataset, ml_model): ml_model})

        for future in concurrent.futures.as_completed(futures):
            ml_model = futures[future]
            result = future.result()
            if result:
                _complete += 1

    print(f"--- Success models: {_complete} ---")
    return _complete


def perform_model_train(test_suite):

    MLModel.objects.filter(
        test_suite_id=test_suite.id,
        dataset_status=MLModel.Status.SUCCESS,
        model_status=MLModel.Status.PENDING
    ).update(model_status=MLModel.Status.PROCESSING)

    model_path, model_filename = MLModel.get_model_filepath(test_suite=test_suite)
    model_path.mkdir(parents=True, exist_ok=True)
    try:
        mlt = MLTrainer(test_suite_id=test_suite.id)
        result = mlt.train()

        MLModel.objects.filter(
            test_suite_id=test_suite.id,
            dataset_status=MLModel.Status.SUCCESS,
            model_status=MLModel.Status.PROCESSING
        ).update(model_status=MLModel.Status.SUCCESS)

    except Exception as e:
        MLModel.objects.filter(
            test_suite_id=test_suite.id,
            dataset_status=MLModel.Status.SUCCESS,
            model_status=MLModel.Status.PROCESSING
        ).update(model_status=MLModel.Status.FAILURE)
        raise e
    return result
