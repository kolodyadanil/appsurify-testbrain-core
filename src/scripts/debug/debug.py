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
from applications.ml.network import TestPrioritizationCBM
from applications.vcs.models import Commit
from applications.testing.models import Test



ml_model = MLModel.objects.get(id=133)

tp = TestPrioritizationCBM(ml_model=ml_model)
tp.train()

