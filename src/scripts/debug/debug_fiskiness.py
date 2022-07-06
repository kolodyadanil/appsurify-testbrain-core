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
from applications.testing.utils.prediction.riskiness.slow_model import update_slow_commits_metrics


# fcr_rfcm = FastCommitRiskinessRFCM(project_id=469)
# fcr_rfcm.train()
# r = fcr_rfcm.predict(commit_sha_list=[])
# print(r)
#
# fcr_rfcm = SlowCommitRiskinessRFCM(project_id=469)
# fcr_rfcm.train()
# r = fcr_rfcm.predict(commit_sha_list=[])
# print(r)

# start_time = time.time()
#
# update_slow_commits_metrics(project_id=469)
#
# print("--- %s seconds ---" % (time.time() - start_time))
