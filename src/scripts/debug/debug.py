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


tpcbm = TestPrioritizationNLPCBM(organization_id=70, project_id=426, test_suite_id=299)
tpcbm.train()
print(tpcbm.is_fitted)
