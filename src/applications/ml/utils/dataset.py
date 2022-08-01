import pathlib
import typing
import glob
import concurrent.futures

from django.db import connection
from django.conf import settings

from .database import psql_execute_query
from .log import logger
from .functional import Statistic


def get_dataset_directory(organization_id: int, project_id: int, test_suite_id: int,
                          index: int) -> pathlib.PosixPath:
    directory = pathlib.PosixPath(settings.STORAGE_ROOT) / "machine_learning" / "priority" / \
                str(organization_id) / str(project_id) / "datasets" / str(test_suite_id) / str(index)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_dataset_filename(test_id: int) -> str:
    filename = f"{test_id}.json"
    return filename


def get_dataset_filelist(organization_id: int, project_id: int, test_suite_id: int, index: int,
                         test_ids: typing.List[int]) -> typing.List[pathlib.PosixPath]:
    file_paths = []
    dataset_directory = get_dataset_directory(
        organization_id=organization_id,
        project_id=project_id,
        test_suite_id=test_suite_id,
        index=index
    )
    for test_id in test_ids:
        file_path = dataset_directory / get_dataset_filename(test_id)
        if file_path.exists():
            file_paths.append(file_path)
    return file_paths


def get_nlp_dataset_filelist(organization_id: int, project_id: int, test_suite_id: int) -> typing.List[pathlib.PosixPath]:
    directory = pathlib.PosixPath(settings.STORAGE_ROOT) / "machine_learning" / "priority" / \
                str(organization_id) / str(project_id) / "datasets" / str(test_suite_id)
    directory.mkdir(parents=True, exist_ok=True)

    file_paths = list(map(pathlib.PosixPath, glob.glob(f"{directory / '*' / '*.json'}")))
    return file_paths


def get_dataset_test_ids(test_suite_id: int, from_date, to_date) -> typing.List[int]:
    sql_template_filepath = settings.BASE_DIR / "applications" / "ml" / "sql" / "test.sql"
    sql_template = open(sql_template_filepath, "r", encoding="utf-8").read()

    sql = sql_template.format(test_suite_id=test_suite_id, min_date=from_date, max_date=to_date)
    with connection.cursor() as cursor:
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

    test_ids = list([row["test_id"] for row in rows])
    return list(set(test_ids))


def dataset_sql(test_suite_id: int, test_id: int, from_date, to_date) -> str:
    sql_template_filepath = settings.BASE_DIR / "applications" / "ml" / "sql" / "dataset.sql"
    sql_template = open(sql_template_filepath, "r", encoding="utf-8").read()
    sql = sql_template.format(test_suite_id=test_suite_id, test_id=test_id, min_date=from_date, max_date=to_date)
    return sql


def dataset_export_sql(organization_id:int, project_id: int, test_suite_id: int, index: int, test_id: int,
                       from_date, to_date) -> str:
    dataset_sql_query = dataset_sql(
        test_suite_id=test_suite_id,
        test_id=test_id,
        from_date=from_date,
        to_date=to_date
    )
    dataset_path = get_dataset_directory(organization_id=organization_id, project_id=project_id,
                                         test_suite_id=test_suite_id, index=index)
    dataset_path.mkdir(parents=True, exist_ok=True)

    dataset_filename = get_dataset_filename(test_id=test_id)

    sql_query = f"\copy (SELECT array_to_json(array_agg(row_to_json(t))) FROM ({dataset_sql_query}) t) " \
                f"To '{dataset_path / dataset_filename}'"
    return sql_query


def export_dataset_to_file(organization_id: int, project_id: int, test_suite_id: int, index: int,
                           test_id: int, from_date, to_date) -> bool:

    logger.debug(f"{test_suite_id} [{index}] preparing for the <Test: {test_id}>")
    export_sql = dataset_export_sql(organization_id=organization_id, project_id=project_id, test_suite_id=test_suite_id,
                                    index=index, test_id=test_id, from_date=from_date, to_date=to_date)
    try:
        output = psql_execute_query(query=export_sql)
        result = True
        logger.debug(f"{test_suite_id} [{index}] complete preparing for the <Test: {test_id}>")
    except Exception as exc:
        logger.exception(f"{test_suite_id} [{index}] error preparing for the <Test: {test_id}>", exc_info=True)
        result = False
    return result


def export_datasets(organization_id: int, project_id: int, test_suite_id: int, index: int,
                    test_ids: typing.List[int], from_date, to_date, max_workers: typing.Optional[int] = 20):

    stats = Statistic()
    stats.total = len(test_ids)

    logger.info(f"{stats} {test_suite_id} [{index}] tests for preparing datasets for the model are selected")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_test_id = {
            executor.submit(
                export_dataset_to_file,
                organization_id=organization_id,
                project_id=project_id,
                test_suite_id=test_suite_id,
                index=index,
                test_id=test_id,
                from_date=from_date,
                to_date=to_date
            )
            : test_id for test_id in test_ids
        }

        for future in concurrent.futures.as_completed(future_to_test_id):
            stats.increase_current()

            test_id = future_to_test_id[future]
            result = future.result()

            if result:
                stats.increase_success()
            else:
                stats.increase_failure()

            if stats.progress_percent % 10 == 0:
                logger.debug(f"{stats} {test_suite_id} [{index}] preparing datasets for tests")

    logger.info(f"{stats} {test_suite_id} [{index}] prepared datasets for tests")
    return stats.success


