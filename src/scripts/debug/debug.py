# -*- coding: utf-8 -*-
import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "system.settings")
django.setup()


import time
import glob
import io
import pathlib
import pandas as pd
from django.db.models import F
from applications.ml.models import *
from applications.ml.utils.dataset import export_datasets
from applications.ml.network import *
from applications.ml.commands import *
from applications.vcs.models import Commit
from applications.testing.models import Test, TestSuite

# tpcbm = TestPrioritizationNLPCBM(organization_id=73, project_id=469, test_suite_id=346)
# print(tpcbm.is_fitted)
#
# queryset = TestSuite.objects.filter(project_id=469)
#
# for test_suite in queryset:
#     s_time = time.time()
#     print(f"Start: {test_suite.id}")
#     tpNLPCBM = MLModel.train_nlp_model(test_suite_id=test_suite.id)
#     print(f"{test_suite.id} - {tpNLPCBM.is_fitted} [ {int(time.time() - s_time)} ]")
#
#
# create_and_check_models()
#
# perform_prepare_datasets()
# perform_train_models()
#
# tpcbm = TestPrioritizationNLPCBM(organization_id=73, project_id=469, test_suite_id=346)
# print(tpcbm.is_fitted)
#
# df = tpcbm._read_file("./scripts/debug/predict_test_suite_346_desktop.json")
# print(df.head())
#
# predicts_df = tpcbm._predict(df)
# print(predicts_df.head())
