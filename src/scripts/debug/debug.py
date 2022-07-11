# -*- coding: utf-8 -*-
import sys

import django

django.setup()

from django.conf import settings
import time
import glob
import io
import pathlib
import pandas as pd
# from django.db.models import F
# from applications.ml.models import States, MLModel, create_sequence
# from applications.ml.utils.dataset import export_datasets
# from applications.ml.network import TestPrioritizationCBM
# from applications.vcs.models import Commit
# from applications.testing.models import Test


def _read_file(file) -> pd.DataFrame:
    """ Clean spec symbols """
    data = open(file, "r").read()
    if data:
        data = data.replace("\\\\", "\\")
        file = io.StringIO(data)
        df = pd.read_json(file)
    else:
        df = pd.DataFrame()
    return df

data_dir = pathlib.PosixPath(settings.STORAGE_ROOT) / "machine_learning" / "priority" / "1" / "2" / "datasets" / "*" / "*"
print(data_dir)
file_list = glob.glob(f"{data_dir / '*.json'}")

for file in file_list:
    print(file)
    df = _read_file(file)
    print(f"\t{df.shape}")
print()

