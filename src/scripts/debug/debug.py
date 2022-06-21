# -*- coding: utf-8 -*-
import django

django.setup()

from applications.vcs.models import Commit
from applications.testing.models import TestSuite, TestRun, Test
from applications.ml.network import *


from applications.ml.models import MLModel


# test_suites = TestSuite.objects.filter(project_id__in=[426, 469]).distinct().order_by("project_id")
# for test_suite in test_suites:
#     MLModel.create_sequence(test_suite_id=test_suite.id)
#
#
# ml_model_queryset = MLModel.objects.filter(
#     test_suite__project_id__in=[
#         426,
#         469
#     ],
#     test_suite_id__in=[346]
#
# ).order_by("test_suite", "index", "updated")[:10]
#
#
# for ml_model in ml_model_queryset:
#     ml_model.save()
#     try:
#         print(f"Prepare <TestSuite: {ml_model.test_suite.id}>")
#         result = ml_model.prepare()
#         print(f"<TestSuite: {ml_model.test_suite.id}> - {result}")
#     except Exception as e:
#         print(f"<TestSuite: {ml_model.test_suite.id}> - {e}")
#         continue

# ml_model = MLModel.objects.get(test_suite_id=346, index=4)
# result = ml_model.train()

