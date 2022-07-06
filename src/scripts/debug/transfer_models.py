import shutil
import typing
import pathlib

from django.conf import settings
from applications.ml.models import  MLModel
from applications.ml.utils.model import get_model_directory, get_model_filename

def get_model_directory_2(organization_id: int, project_id: int, test_suite_id: int, index: int) -> pathlib.PosixPath:
    directory = pathlib.PosixPath(settings.STORAGE_ROOT) / "machine_learning" / "priority" / \
                str(organization_id) / str(project_id) / "models" / str(test_suite_id) / str(index)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_model_filename_2(test_suite_id: int, extension: typing.Optional[str] = "cbm"):
    filename = f"{test_suite_id}.{extension}"
    return filename

for ml in MLModel.objects.all():
    pid = ml.test_suite.project_id
    oid = ml.test_suite.project.organization_id
    tid = ml.test_suite_id
    i = ml.index
    src = get_model_directory(oid, pid, tid, i) / get_model_filename(tid)
    dst = get_model_directory_2(oid, pid, tid, i) / get_model_filename_2(tid)
    print(f"{src} >> {dst}")
    if not src.exists():
        print("\tSKIPPED")
        continue
    shutil.copy(src, dst)
    print("\tCOPIED")