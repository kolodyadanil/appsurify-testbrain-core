# -*- coding: utf-8 -*-
import sys

import django

django.setup()

import time

import pandas as pd
from django.db.models import F
from applications.ml.models import States, MLModel, create_sequence
from applications.ml.utils.dataset import export_datasets
from applications.ml.network import *
from applications.vcs.models import Commit
from applications.testing.models import Test


fcr_rfcm = FastCommitRiskinessRFCM(project_id=487)
fcr_rfcm.train()
r = fcr_rfcm.predict(commit_sha_list=[])
print(r)
