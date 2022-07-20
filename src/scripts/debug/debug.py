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
from django.db.models import F
from applications.ml.models import States, MLModel, create_sequence
from applications.ml.utils.dataset import export_datasets
from applications.ml.network import *
from applications.vcs.models import Commit
from applications.testing.models import Test


ml_models = MLModel.objects.filter(test_suite__project_id=469).order_by("test_suite", "index")

for ml_model in ml_models:
    organization_id = int(ml_model.test_suite.project.organization_id)
    project_id = int(ml_model.test_suite.project_id)
    test_suite_id = int(ml_model.test_suite_id)
    index = ml_model.index
    test_ids = list(ml_model.tests.values_list("id", flat=True))
    result = export_datasets(
        organization_id=organization_id,
        project_id=project_id,
        test_suite_id=test_suite_id,
        index=index,
        test_ids=test_ids,
        from_date=ml_model.from_date,
        to_date=ml_model.to_date
    )
    print(result)