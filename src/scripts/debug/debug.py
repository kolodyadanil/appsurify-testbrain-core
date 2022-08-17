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

# ml_model = MLModel.objects.get(id=161)
# tpcbm = TestPrioritizationNLPCBM(ml_model=ml_model)
# tpcbm.train()
# print(tpcbm.is_fitted)
queryset = TestSuite.objects.filter(models__isnull=True, project__id__exact=671).distinct().order_by("project_id")

time_threshold = datetime.now() - timedelta(weeks=2)
queryset = MLModel.objects.filter(created__lt=time_threshold, state__in=MLStates.values, test_suite__project__id__exact=671).order_by("test_suite_id").distinct("test_suite_id")

