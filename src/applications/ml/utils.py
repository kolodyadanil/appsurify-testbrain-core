# -*- coding: utf-8 -*-
import pathlib
import time
import os
import subprocess
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from applications.ml.models import MLModel
from applications.ml.neural_network import MLTrainer
from applications.testing.models import TestSuite


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
        raise Exception(stderr)
    return stdout


def fix_missed_models():
    test_suites = TestSuite.objects.filter(model=None)
    objs = MLModel.objects.bulk_create([
        MLModel(test_suite=test_suite)
        for test_suite in test_suites
    ])
    return len(objs)


def fix_expired_models(days=7):
    queryset = MLModel.objects\
        .filter(dataset_status=MLModel.Status.SUCCESS)\
        .filter(updated__lte=datetime.now(timezone.utc) - timedelta(days=days))
    queryset.update(dataset_status=MLModel.Status.PENDING, model_status=MLModel.Status.PENDING)


def fix_broken_models(days=7):
    queryset = MLModel.objects\
        .filter(dataset_status=MLModel.Status.FAILURE)\
        .filter(updated__gte=datetime.now(timezone.utc) - timedelta(days=days))
    queryset.update(dataset_status=MLModel.Status.PENDING)

    queryset = MLModel.objects\
        .filter(model_status=MLModel.Status.FAILURE)\
        .filter(updated__gte=datetime.now(timezone.utc) - timedelta(days=days))
    queryset.update(model_status=MLModel.Status.PENDING)


def perform_dataset_to_csv(ml_model):

    ml_model.dataset_status = MLModel.Status.PROCESSING
    ml_model.save()

    dataset_path, dataset_filename = ml_model.dataset_path
    dataset_path.mkdir(parents=True, exist_ok=True)

    sql_query = f"\copy ({ml_model.dataset_sql}) To '{dataset_path / dataset_filename}' With CSV DELIMITER ',' HEADER"

    try:
        ret = execute_query(query=sql_query)

        ml_model.dataset_status = MLModel.Status.SUCCESS
        ml_model.model_status = MLModel.Status.PENDING
        ml_model.save()
    except Exception as e:
        ml_model.dataset_status = MLModel.Status.FAILURE
        ml_model.save()
        raise e


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
