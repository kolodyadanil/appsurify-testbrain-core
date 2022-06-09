# -*- coding: utf-8 -*-

import concurrent.futures
import os
import subprocess
from django.conf import settings


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


def processing_dataset(ml_model, test):
    result = False
    dataset_filename = ml_model.dataset_filename.format(test_id=test.id)
    dataset_path = ml_model.dataset_path
    dataset_path.mkdir(parents=True, exist_ok=True)
    test_id = test.id

    sql = ml_model.dataset_sql(test)
    sql_query = f"\copy ({sql}) To '{dataset_path / dataset_filename}' With CSV DELIMITER ',' HEADER"

    try:
        output = execute_query(query=sql_query)
        result = True
        print(f"PREPARE DATASET <TestSuiteID: {ml_model.test_suite_id}> <TestID: {test_id}> (SUCCESS '{output}')")
    except Exception as e:
        print(f"PREPARE DATASET <TestSuiteID: {ml_model.test_suite_id}> <TestID: {test_id}> (FAIL {str(e)})")

    return result


def prepare_dataset_to_csv(ml_model, max_workers=20):
    _total = 0
    _success = 0
    _fail = 0
    _current = 0

    tests = ml_model.tests.all()

    _total = tests.count()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:

        futures = {}
        for test in tests:
            futures.update({executor.submit(processing_dataset, ml_model, test): ml_model})

        for future in concurrent.futures.as_completed(futures):
            ml_model = futures[future]
            result = future.result()

            _current += 1

            if result:
                _success += 1
            else:
                _fail += 1

            if (_current * 100 // _total) >= 10:
                _current = 0
                print(f"PREPARE DATASET <TestSuiteID: {ml_model.test_suite_id}> "
                      f"(TOTAL: {_total} / SUCCESS: {_success} / FAIL: {_fail})")

    print(f"PREPARE DATASET <TestSuiteID: {ml_model.test_suite_id}> "
          f"(TOTAL: {_total} / SUCCESS: {_success} / FAIL: {_fail})")

    return _success
