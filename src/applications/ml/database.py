import os
import subprocess
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from django.conf import settings
from applications.ml.utils import logger, Statistic


stats = Statistic()
lock = Lock()


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
        logger.exception(f"An error occurred while executing '{psql_cmd}' {stderr}", exc_info=True)
        raise QueryException(stderr)
    return stdout


def processing_dataset(ml_model, test):
    global stats
    result = False

    logger.debug(f"{stats} {ml_model} preparing for the <Test: {test.id}>")

    dataset_filename = ml_model.dataset_filename.format(test_id=test.id)
    dataset_path = ml_model.dataset_path
    dataset_path.mkdir(parents=True, exist_ok=True)

    sql = ml_model.dataset_sql(test)
    sql_query = f"\copy (SELECT row_to_json(t) FROM ({sql}) t) " \
                f"To '{dataset_path / dataset_filename}'"

    try:
        output = execute_query(query=sql_query)
        logger.debug(f"{stats} {ml_model} complete preparing for the <Test: {test.id}>: {output}")
        result = True
    except Exception as exc:
        logger.exception(f"{stats} {ml_model} error preparing for the <Test: {test.id}>", exc_info=True)
        result = False
    return result


# simple progress indicator callback function
def progress_indicator(future):
    global lock, stats
    # obtain the lock
    with lock:
        # update the counter
        stats.increase_current()

    # check if task was cancelled
    if future.cancelled():
        # the task was cancelled
        ...
    elif future.exception():
        # the task raised an exception
        ...
    else:
        # the task finished successfully
        result = future.result()
        if result:
            stats.increase_success()
        else:
            stats.increase_failure()

    if stats.progress_percent % 10 == 0:
        logger.debug(f"{stats} {stats.context['ml_model']} preparing datasets for tests")


def prepare_dataset_to_file(ml_model, max_workers=20):
    global stats
    stats.reset()

    queryset = ml_model.tests.all()
    stats.total = queryset.count()
    stats.context = {"ml_model": ml_model}

    logger.info(f"{stats} {ml_model} tests for preparing datasets for the model are selected")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_test = {
            executor.submit(processing_dataset, ml_model, test):
                (ml_model, test) for test in queryset}

        for future in as_completed(future_to_test):
            future.add_done_callback(progress_indicator)

    logger.info(f"{stats} {stats.context['ml_model']} prepared datasets for tests")
    return stats.success
