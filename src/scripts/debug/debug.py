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


tpNLPCBM = MLModel.train_nlp_model(project_id=469)
print(tpNLPCBM.is_fitted)





print("Finish")
