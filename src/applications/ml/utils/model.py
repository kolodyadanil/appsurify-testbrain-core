import typing
import pathlib

from django.conf import settings


def get_model_directory(organization_id: int, project_id: int, test_suite_id: int) -> pathlib.PosixPath:
    directory = pathlib.PosixPath(settings.STORAGE_ROOT) / "machine_learning" / "priority" / \
                str(organization_id) / str(project_id) / "models" / str(test_suite_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_model_filename(test_suite_id: int, index: int, extension: typing.Optional[str] = "cbm"):
    filename = f"{test_suite_id}.{index}.{extension}"
    return filename


def get_nlp_model_filename(test_suite_id: int, extension: typing.Optional[str] = "cbm"):
    filename = f"{test_suite_id}.nlp.{extension}"
    return filename


def predict_sql(test_ids: typing.List[int], commit_ids: typing.List[int]) -> str:
    sql_template_filepath = settings.BASE_DIR / "applications" / "ml" / "sql" / "predict.sql"
    sql_template = open(sql_template_filepath, "r", encoding="utf-8").read()

    test_ids_str = str(', '.join(map(str, test_ids)))
    commit_ids_str = str(', '.join(map(str, commit_ids)))

    sql = sql_template.format(test_ids=test_ids_str, commit_ids=commit_ids_str)
    return sql


def get_riskiness_model_directory(organization_id: int, project_id: int) -> pathlib.PosixPath:
    directory = pathlib.PosixPath(settings.STORAGE_ROOT) / "machine_learning" / "riskiness" / \
                str(organization_id) / str(project_id) / "models"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_riskiness_model_filename(analyze_type: str, extension: typing.Optional[str] = "pkl") -> str:
    filename = f"{analyze_type}.{extension}"
    return filename
