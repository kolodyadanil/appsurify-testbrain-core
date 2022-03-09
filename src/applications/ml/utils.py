# -*- coding: utf-8 -*-
import pathlib
import time
import os
import subprocess
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from applications.ml.models import MLDataset, MLModel
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


def fix_missed_datasets():
    test_suites = TestSuite.objects.filter(dataset=None)
    objs = MLDataset.objects.bulk_create([
        MLDataset(test_suite=test_suite) for test_suite in test_suites
    ])
    return len(objs)


def fix_expired_datasets(days=7):
    datasets = MLDataset.objects\
        .filter(status=MLDataset.Status.SUCCESS)\
        .filter(updated__lte=datetime.now(timezone.utc) - timedelta(days=days))
    datasets.update(status=MLDataset.Status.PENDING)


def fix_broken_datasets(days=2):
    datasets = MLDataset.objects\
        .exclude(status=MLDataset.Status.SUCCESS)\
        .filter(updated__gte=datetime.now(timezone.utc) - timedelta(days=days))
    datasets.update(status=MLDataset.Status.PENDING)


def fix_missed_models():
    test_suites = TestSuite.objects.filter(model=None, dataset__status=MLDataset.Status.SUCCESS)
    objs = MLModel.objects.bulk_create([
        MLModel(test_suite=test_suite) for test_suite in test_suites
    ])
    return len(objs)


def fix_expired_models(days=7):
    datasets = MLModel.objects\
        .filter(status=MLModel.Status.SUCCESS)\
        .filter(updated__lte=datetime.now(timezone.utc) - timedelta(days=days))
    datasets.update(status=MLModel.Status.PENDING)


def fix_broken_models(days=2):
    datasets = MLModel.objects\
        .exclude(status=MLModel.Status.SUCCESS)\
        .filter(updated__gte=datetime.now(timezone.utc) - timedelta(days=days))
    datasets.update(status=MLModel.Status.PENDING)


def perform_dataset_to_csv(ml_dataset):

    ml_dataset.status = MLDataset.Status.STARTED
    ml_dataset.save(update_fields=["status", ])

    sql_template = open(settings.BASE_DIR / "applications" / "ml" / "sql" / "dataset.sql", "r", encoding="utf-8").read()
    sql = sql_template.format(test_suite_id=ml_dataset.test_suite_id)

    dir, filename = ml_dataset.path
    dir.mkdir(parents=True, exist_ok=True)

    sql_query = f"\copy ({sql}) To '{dir / filename}' With CSV DELIMITER ',' HEADER"

    try:
        ret = execute_query(query=sql_query)
        print(ret)
    except Exception as e:
        ml_dataset.status = MLDataset.Status.FAILURE
        ml_dataset.save(update_fields=["status", ])
        raise e

    ml_dataset.status = MLDataset.Status.SUCCESS
    ml_dataset.save(update_fields=["status", ])


def perform_model_train(ml_model):

    ml_model.status = MLModel.Status.STARTED
    ml_model.save(update_fields=["status", ])

    dir, filename = ml_model.path
    dir.mkdir(parents=True, exist_ok=True)

    try:
        mlt = MLTrainer(test_suite_id=ml_model.test_suite.id)
        mlt.train()
    except Exception as e:
        ml_model.status = MLModel.Status.FAILURE
        ml_model.save(update_fields=["status", ])
        raise e

    ml_model.status = MLModel.Status.SUCCESS
    ml_model.save(update_fields=["status", ])
