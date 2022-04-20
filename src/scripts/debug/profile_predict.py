# -*- coding: utf-8 -*-
import django

django.setup()

from applications.vcs.models import Commit
from applications.testing.models import TestSuite, TestRun, Test
from applications.ml.network import *

print("HELLO!")

percent = 30
project_id = 469
test_suite_id = 346

commit_ids = [703010, ]
test_ids = [60304, 60305, 60562, 60564, 60299, 60304, 60305, 60306, 60309, 60310]


commits_queryset = Commit.objects.filter(id__in=commit_ids)
tests_queryset = Test.objects.filter(id__in=test_ids)
test_suite = TestSuite.objects.get(id=test_suite_id)


# Predict id ML trained
print("START PREDICT")
print(f"LEN: {len(test_ids)}")
ml_predictor = MLPredictor(test_suite_id=test_suite_id)
ml_model_existing_flag = ml_predictor.is_loaded
result = ml_predictor.get_test_prioritization(tests_queryset, commits_queryset)
print(result)
print("PREDICTED")

# Train ML
# print("DO Train!")
# mlt = MLTrainer(test_suite_id=test_suite_id)
# mlt.train()
